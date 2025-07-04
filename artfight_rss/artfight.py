"""ArtFight API client for scraping profile data and team standings."""

import html
import logging
import re
from datetime import datetime, timedelta
from urllib.parse import urljoin
import asyncio

import httpx
from bs4 import BeautifulSoup, Tag
from pydantic import HttpUrl, parse_obj_as

from .cache import RateLimiter
from .database import ArtFightDatabase
from .config import settings
from .models import ArtFightAttack, ArtFightDefense, TeamStanding

# Set up logging
logger = logging.getLogger(__name__)


class ArtFightClient:
    """Client for interacting with ArtFight."""

    def __init__(self, rate_limiter: RateLimiter, database: ArtFightDatabase) -> None:
        """Initialize ArtFight client."""
        self.base_url = settings.artfight_base_url
        self.rate_limiter = rate_limiter
        self.database = database
        
        # Authentication validation cache (5 minutes)
        self._auth_cache = {
            'is_valid': None,
            'last_check': None,
            'cache_duration': timedelta(minutes=5)
        }
        
        logger.debug(f"Initializing ArtFight client with base URL: {self.base_url}")
        
        # Set up headers to match the working test exactly
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-GPC": "1",
            "Pragma": "no-cache",
            "Cache-Control": "no-cache"
        }
        
        logger.debug(f"Request headers: {headers}")
        
        # Add authentication cookies if provided
        self.cookies = {}
        if settings.laravel_session:
            self.cookies["laravel_session"] = settings.laravel_session
            logger.debug(f"Laravel session cookie configured (length: {len(settings.laravel_session)})")
        else:
            logger.debug("No Laravel session cookie configured")
            
        if settings.cf_clearance:
            self.cookies["cf_clearance"] = settings.cf_clearance
            logger.debug(f"CF clearance cookie configured (length: {len(settings.cf_clearance)})")
        else:
            logger.debug("No CF clearance cookie configured")
            
        if settings.remember_web:
            self.cookies["remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d"] = settings.remember_web
            logger.debug(f"Remember web cookie configured (length: {len(settings.remember_web)})")
        else:
            logger.debug("No remember web cookie configured")
        
        logger.debug(f"Cookies configured: {list(self.cookies.keys())}")
        
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers=headers,
            cookies=self.cookies
        )
        
        logger.debug("ArtFight client initialized successfully")

    def _log_request(self, method: str, url: str, **kwargs) -> None:
        """Log HTTP request details."""
        logger.debug(f"HTTP {method.upper()} request to: {url}")
        if 'cookies' in kwargs and kwargs['cookies']:
            cookie_info = {}
            for key, value in kwargs['cookies'].items():
                if key in ['laravel_session', 'cf_clearance', 'remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d']:
                    # Show first and last few characters for security
                    if len(value) > 8:
                        cookie_info[key] = f"{value[:4]}...{value[-4:]}"
                    else:
                        cookie_info[key] = f"{value[:2]}...{value[-2:]}"
                else:
                    cookie_info[key] = value
            logger.debug(f"Request cookies: {cookie_info}")
        if 'headers' in kwargs and kwargs['headers']:
            logger.debug(f"Request headers: {dict(kwargs['headers'])}")

    def _log_response(self, response: httpx.Response) -> None:
        """Log HTTP response details."""
        logger.debug(f"HTTP response: {response.status_code} {response.reason_phrase}")
        logger.debug(f"Response URL: {response.url}")
        logger.debug(f"Response headers: {dict(response.headers)}")
        if response.cookies:
            cookie_info = {}
            for key, value in response.cookies.items():
                if key in ['laravel_session', 'cf_clearance', 'remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d']:
                    # Show first and last few characters for security
                    if len(value) > 8:
                        cookie_info[key] = f"{value[:4]}...{value[-4:]}"
                    else:
                        cookie_info[key] = f"{value[:2]}...{value[-2:]}"
                else:
                    cookie_info[key] = value
            logger.debug(f"Response cookies: {cookie_info}")
            
            # Only refresh cookies on successful responses (200)
            if response.status_code == 200:
                self._refresh_cookies_from_response(response)
            else:
                # Log but don't refresh on non-200 responses
                if 'laravel_session' in response.cookies:
                    logger.debug("New Laravel session cookie received but not refreshed (non-200 response)")
                if 'cf_clearance' in response.cookies:
                    logger.debug("New CF clearance cookie received but not refreshed (non-200 response)")
        
        # Log redirect chain if any
        if response.history:
            logger.debug("Redirect chain:")
            for hist_response in response.history:
                logger.debug(f"  {hist_response.status_code} -> {hist_response.url}")
            logger.debug(f"  Final: {response.status_code} -> {response.url}")

    def _refresh_cookies_from_response(self, response: httpx.Response) -> None:
        """Refresh cookies from a successful response."""
        if not response.cookies:
            return

        cookies_updated = False
        
        # Update Laravel session cookie
        if 'laravel_session' in response.cookies:
            new_session = response.cookies['laravel_session']
            if new_session != self.cookies.get('laravel_session'):
                self.cookies['laravel_session'] = new_session
                cookies_updated = True
                logger.info(f"Updated Laravel session cookie: {new_session[:4]}...{new_session[-4:]}")
        
        # Update CF clearance cookie
        if 'cf_clearance' in response.cookies:
            new_clearance = response.cookies['cf_clearance']
            if new_clearance != self.cookies.get('cf_clearance'):
                self.cookies['cf_clearance'] = new_clearance
                cookies_updated = True
                logger.info(f"Updated CF clearance cookie: {new_clearance[:4]}...{new_clearance[-4:]}")
        
        # Update remember web cookie
        if 'remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d' in response.cookies:
            new_remember = response.cookies['remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d']
            if new_remember != self.cookies.get('remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d'):
                self.cookies['remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d'] = new_remember
                cookies_updated = True
                logger.info(f"Updated remember web cookie: {new_remember[:4]}...{new_remember[-4:]}")
        
        if cookies_updated:
            # Update the httpx client with new cookies
            self.client.cookies.update(self.cookies)
            logger.info("Client cookies updated successfully")
            
            # Clear authentication cache since cookies changed
            self.clear_auth_cache()

    async def get_user_attacks(self, username: str) -> list[ArtFightAttack]:
        """Get attacks for a specific user with pagination."""
        logger.debug(f"Fetching attacks for user: {username}")
        
        # Check rate limit
        if not self.rate_limiter.can_request(f"attacks_{username}"):
            # Return existing data from database if rate limited
            logger.debug(f"Rate limited for attacks_{username}, returning existing attacks from database")
            return self.database.get_attacks_for_user(username)

        try:
            # Check authentication first if session cookie is provided
            if settings.laravel_session and not await self.validate_authentication():
                logger.warning("Authentication failed for attacks - session cookie may be invalid")
                return []

            all_attacks = []
            page = 1
            base_url = urljoin(self.base_url, f"/~{username}/attacks")
            
            while True:
                # Construct URL for current page
                if page == 1:
                    page_url = base_url
                else:
                    page_url = f"{base_url}?page={page}"
                
                logger.debug(f"Fetching attacks page {page}: {page_url}")
                self._log_request("GET", page_url, cookies=self.cookies)
                
                response = await self.client.get(page_url)
                self._log_response(response)
                response.raise_for_status()

                # Parse attacks from the page
                logger.debug(f"Parsing attacks from HTML (content length: {len(response.text)})")
                page_attacks = self._parse_attacks_from_html(response.text, username)
                
                logger.debug(f"Found {len(page_attacks)} attacks on page {page}")
                all_attacks.extend(page_attacks)
                
                # If no attacks found on first page, stop pagination
                if page == 1 and not page_attacks:
                    logger.debug("No attacks found on first page, stopping pagination")
                    break
                
                # Check if there's a next page
                if not self._has_next_page(response.text):
                    logger.debug(f"No more pages found, stopping at page {page}")
                    break
                
                # Add delay before next page request
                if page < 10:  # Limit to reasonable number of pages
                    delay = self._calculate_page_delay()
                    logger.debug(f"Waiting {delay:.2f} seconds before next page request")
                    await asyncio.sleep(delay)
                    page += 1
                else:
                    logger.warning(f"Reached maximum page limit ({page}), stopping pagination")
                    break

            # Save attacks to database
            if all_attacks:
                self.database.save_attacks(all_attacks)

            # Record the request
            self.rate_limiter.record_request(f"attacks_{username}")

            logger.debug(f"Successfully fetched {len(all_attacks)} attacks for user {username} across {page} pages")
            return all_attacks

        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching attacks for {username}: {e}")
            # Try to get response from the exception
            try:
                response = getattr(e, 'response', None)
                if response:
                    self._log_response(response)
            except Exception:
                pass
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching attacks for {username}: {e}")
            return []

    async def get_user_defenses(self, username: str) -> list[ArtFightDefense]:
        """Get defenses for a specific user with pagination."""
        logger.debug(f"Fetching defenses for user: {username}")
        
        # Check rate limit
        if not self.rate_limiter.can_request(f"defenses_{username}"):
            # Return existing data from database if rate limited
            logger.debug(f"Rate limited for defenses_{username}, returning existing defenses from database")
            return self.database.get_defenses_for_user(username)

        try:
            # Check authentication first if session cookie is provided
            if settings.laravel_session and not await self.validate_authentication():
                logger.warning("Authentication failed for defenses - session cookie may be invalid")
                return []

            all_defenses = []
            page = 1
            base_url = urljoin(self.base_url, f"/~{username}/defenses")
            
            while True:
                # Construct URL for current page
                if page == 1:
                    page_url = base_url
                else:
                    page_url = f"{base_url}?page={page}"
                
                logger.debug(f"Fetching defenses page {page}: {page_url}")
                self._log_request("GET", page_url, cookies=self.cookies)
                
                response = await self.client.get(page_url)
                self._log_response(response)
                response.raise_for_status()

                # Parse defenses from the page
                logger.debug(f"Parsing defenses from HTML (content length: {len(response.text)})")
                page_defenses = self._parse_defenses_from_html(response.text, username)
                
                logger.debug(f"Found {len(page_defenses)} defenses on page {page}")
            
                existing_defense_ids = self.database.get_existing_defense_ids(username)
                new_defenses = [d for d in page_defenses if d.id not in existing_defense_ids]
                logger.debug(f"Found {len(new_defenses)} new defenses out of {len(page_defenses)} total on first page")
                
                # If no new defenses found on first page, stop pagination
                if not new_defenses:
                    logger.debug("No new defenses found, stopping pagination")
                    break
                
                all_defenses.extend(page_defenses)
                
                # Check if there's a next page
                if not self._has_next_page(response.text):
                    logger.debug(f"No more pages found, stopping at page {page}")
                    break
                
                # Add delay before next page request
                if page < 10:  # Limit to reasonable number of pages
                    delay = self._calculate_page_delay()
                    logger.debug(f"Waiting {delay:.2f} seconds before next page request")
                    await asyncio.sleep(delay)
                    page += 1
                else:
                    logger.warning(f"Reached maximum page limit ({page}), stopping pagination")
                    break

            # Save defenses to database
            if all_defenses:
                self.database.save_defenses(all_defenses)

            # Record the request
            self.rate_limiter.record_request(f"defenses_{username}")

            logger.debug(f"Successfully fetched {len(all_defenses)} defenses for user {username} across {page} pages")
            # return defenses from db
            return self.database.get_defenses_for_user(username)

        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching defenses for {username}: {e}")
            # Try to get response from the exception
            try:
                response = getattr(e, 'response', None)
                if response:
                    self._log_response(response)
            except Exception:
                pass
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching defenses for {username}: {e}")
            return []

    async def validate_authentication(self) -> bool:
        """Validate that the session cookie is still valid with 5-minute caching."""
        if not settings.laravel_session:
            logger.debug("No Laravel session configured, skipping authentication validation")
            return False
        
        # Check if we have a valid cached result
        now = datetime.now()
        if (self._auth_cache['last_check'] and 
            self._auth_cache['is_valid'] is not None and
            now - self._auth_cache['last_check'] < self._auth_cache['cache_duration']):
            
            logger.debug(f"Using cached authentication result: {self._auth_cache['is_valid']} (cached {now - self._auth_cache['last_check']} ago)")
            return self._auth_cache['is_valid']
        
        # Cache expired or no cache, perform actual validation
        logger.debug("Authentication cache expired or missing, performing validation")
        
        try:
            # Try to access a page that requires authentication
            # ArtFight's profile page or dashboard would be good for this
            test_url = urljoin(self.base_url, "/~fourleafisland/defenses")
            logger.debug("Validating authentication by accessing protected page")
            self._log_request("GET", test_url, cookies=self.cookies)
            
            response = await self.client.get(test_url)
            self._log_response(response)
            
            # Check if we're redirected to login or get an error
            if response.status_code == 302:
                # Redirected to login page
                logger.warning("Authentication validation failed: redirected to login page")
                self._auth_cache['is_valid'] = False
                self._auth_cache['last_check'] = now
                return False
            elif response.status_code == 200:
                # Check if the page contains login elements (indicating we're not logged in)
                soup = BeautifulSoup(response.text, "html.parser")
                login_elements = soup.find_all("a", href="/login") or soup.find_all("form", action="/login")
                is_authenticated = len(login_elements) == 0
                logger.debug(f"Authentication validation result: {'success' if is_authenticated else 'failed'} (login elements found: {len(login_elements)})")
                
                # Cache the result
                self._auth_cache['is_valid'] = is_authenticated
                self._auth_cache['last_check'] = now
                
                return is_authenticated
            else:
                logger.warning(f"Authentication validation failed: unexpected status code {response.status_code}")
                self._auth_cache['is_valid'] = False
                self._auth_cache['last_check'] = now
                return False
                
        except Exception as e:
            logger.error(f"Error validating authentication: {e}")
            self._auth_cache['is_valid'] = False
            self._auth_cache['last_check'] = now
            return False

    def get_authentication_info(self) -> dict:
        """Get information about the current authentication status."""
        return {
            "authenticated": bool(settings.laravel_session),
            "laravel_session_configured": bool(settings.laravel_session),
            "cf_clearance_configured": bool(settings.cf_clearance),
            "laravel_session_length": len(settings.laravel_session) if settings.laravel_session else 0,
            "cf_clearance_length": len(settings.cf_clearance) if settings.cf_clearance else 0,
            "current_cookies": {
                "laravel_session": f"{self.cookies.get('laravel_session', '')[:4]}...{self.cookies.get('laravel_session', '')[-4:]}" if self.cookies.get('laravel_session') else None,
                "cf_clearance": f"{self.cookies.get('cf_clearance', '')[:4]}...{self.cookies.get('cf_clearance', '')[-4:]}" if self.cookies.get('cf_clearance') else None
            },
            "auth_cache": {
                "is_valid": self._auth_cache['is_valid'],
                "last_check": self._auth_cache['last_check'],
                "cache_duration": str(self._auth_cache['cache_duration'])
            }
        }

    def clear_auth_cache(self) -> None:
        """Clear the authentication validation cache."""
        self._auth_cache['is_valid'] = None
        self._auth_cache['last_check'] = None
        logger.debug("Authentication cache cleared")

    def _calculate_page_delay(self) -> float:
        """Calculate delay for page requests with wobble."""
        import random
        
        base_delay = settings.page_request_delay_sec
        wobble_factor = settings.page_request_wobble
        
        # Calculate random wobble (±wobble_factor)
        wobble = random.uniform(-wobble_factor, wobble_factor)
        actual_delay = base_delay * (1 + wobble)
        
        # Ensure delay is not negative
        actual_delay = max(0.1, actual_delay)
        
        logger.debug(f"Page delay: {base_delay}s base + {wobble:+.2f} wobble = {actual_delay:.2f}s")
        return actual_delay

    def _parse_attacks_from_html(self, html: str, username: str) -> list[ArtFightAttack]:
        """Parse attacks from HTML content."""
        elements = self._parse_attack_defense_elements(html, username, is_defense=False)
        return [elem for elem in elements if isinstance(elem, ArtFightAttack)]

    def _parse_defenses_from_html(self, html: str, username: str) -> list[ArtFightDefense]:
        """Parse defenses from HTML content."""
        elements = self._parse_attack_defense_elements(html, username, is_defense=True)
        return [elem for elem in elements if isinstance(elem, ArtFightDefense)]

    def _parse_attack_defense_elements(self, html: str, username: str, is_defense: bool) -> list[ArtFightAttack | ArtFightDefense]:
        """Shared parsing function for both attacks and defenses."""
        soup = BeautifulSoup(html, "html.parser")
        elements = []

        # Find all <a> elements with class 'attack-thumb' (ArtFight attack/defense thumbnails)
        thumb_elements = soup.find_all("a", class_="attack-thumb")
        logger.debug(f"Found {len(thumb_elements)} {'defense' if is_defense else 'attack'} thumbnails for user {username}")

        for i, element in enumerate(thumb_elements):
            try:
                logger.debug(f"Parsing {'defense' if is_defense else 'attack'} element {i+1}/{len(thumb_elements)}")
                parsed_element = self._parse_attack_defense_element(element, username, is_defense)
                if parsed_element:
                    elements.append(parsed_element)
                    logger.debug(f"Successfully parsed {'defense' if is_defense else 'attack'}: {parsed_element.title}")
                else:
                    logger.debug(f"Failed to parse {'defense' if is_defense else 'attack'} element {i+1}")
            except Exception as e:
                logger.error(f"Error parsing {'defense' if is_defense else 'attack'} element {i+1}: {e}")
                continue

        logger.debug(f"Successfully parsed {len(elements)} {'defenses' if is_defense else 'attacks'} for user {username}")
        return elements

    def _parse_attack_element(self, element, username: str) -> ArtFightAttack | None:
        """Parse a single attack element from a <a> tag."""
        result = self._parse_attack_defense_element(element, username, is_defense=False)
        return result if isinstance(result, ArtFightAttack) else None

    def _parse_defense_element(self, element, username: str) -> ArtFightDefense | None:
        """Parse a single defense element from a <a> tag."""
        result = self._parse_attack_defense_element(element, username, is_defense=True)
        return result if isinstance(result, ArtFightDefense) else None

    def _parse_attack_defense_element(self, element, username: str, is_defense: bool) -> ArtFightAttack | ArtFightDefense | None:
        """Parse a single attack or defense element from a <a> tag."""
        try:
            # Extract ID from data-id or from the URL
            element_id = element.get("data-id")
            if not element_id:
                # Try to extract from the href
                href = element.get("href", "")
                # e.g. /attack/9390471.office-girlsss
                match = re.search(r"/attack/(\\d+)", href)
                if match:
                    element_id = match.group(1)
                else:
                    element_id = href

            # Extract link
            link = urljoin(self.base_url, element.get("href", ""))
            url_http = parse_obj_as(HttpUrl, link)

            # Extract image
            img_elem = element.find("img")
            image_url_http = None
            if img_elem and img_elem.get("src"):
                image_url = img_elem["src"]
                # If the image URL is absolute, use as is; otherwise, join with base_url
                if image_url.startswith("http"):
                    image_url_http = parse_obj_as(HttpUrl, image_url)
                else:
                    image_url_http = parse_obj_as(HttpUrl, urljoin(self.base_url, image_url))

            # Extract title from title on the <img> tag
            # Can be misleading: popper moves the data to data-original-title in a browser
            title = None
            if img_elem and img_elem.get("title"):
                title = html.unescape(img_elem["title"])
            if not title:
                # Fallback: use alt attribute or default
                alt_text = img_elem.get("alt") if img_elem and img_elem.get("alt") else f"Untitled {'Defense' if is_defense else 'Attack'}"
                title = html.unescape(alt_text)

            # TODO: load from the attack page
            description = None

            # Parse title to extract attacker/defender information
            # Title format is typically "Title by Username" for defenses
            # For attacks, the logic is reversed
            if " by " in title:
                title_part, user_part = title.split(" by ", 1)
                title = title_part.strip()
                other_user = user_part.strip()
            else:
                other_user = "Unknown"

            fetched_at = datetime.now()

            if is_defense:
                # For defenses: profile owner is defender, title contains attacker
                defender = username
                attacker = other_user
                
                return ArtFightDefense(
                    id=element_id,
                    title=title,
                    description=description,
                    image_url=image_url_http,
                    defender_user=defender,
                    attacker_user=attacker,
                    fetched_at=fetched_at,
                    url=url_http
                )
            else:
                # For attacks: profile owner is attacker, title contains attacker
                # FIXME: Need to parse the attack page to get the defender
                attacker = username
                defender = "TODO"
                
                return ArtFightAttack(
                    id=element_id,
                    title=title,
                    description=description,
                    image_url=image_url_http,
                    attacker_user=attacker,
                    defender_user=defender,
                    fetched_at=fetched_at,
                    url=url_http
                )

        except Exception as e:
            print(f"Error parsing {'defense' if is_defense else 'attack'} element: {e}")
            return None

    def _has_next_page(self, html: str) -> bool:
        """Check if there's a next page by looking for disabled 'Next' button."""
        soup = BeautifulSoup(html, "html.parser")
        
        # Look for the "Next" button
        next_button = soup.find("a", class_="page-link", attrs={"aria-label": "Next »"})
        
        if next_button:
            # Check if the button is disabled by looking for disabled class
            is_disabled = "disabled" in str(next_button)
            logger.debug(f"Found Next button, disabled: {is_disabled}")
            return not is_disabled
        
        # If no Next button found, assume we're on the last page
        logger.debug("No Next button found, assuming last page")
        return False

    async def get_team_standings(self) -> list[TeamStanding]:
        """Get current team standings."""
        # Check rate limit
        if not self.rate_limiter.can_request("teams"):
            # Return existing data from database if rate limited
            logger.debug("Rate limited for teams, returning existing standings from database")
            return self.database.get_team_standings()

        try:
            # Check authentication first if session cookie is provided
            if settings.laravel_session and not await self.validate_authentication():
                logger.warning("Authentication failed for team standings - session cookie may be invalid")
                return []

            # Fetch teams page
            teams_url = urljoin(self.base_url, "/")
            logger.debug("Fetching team standings")
            self._log_request("GET", teams_url, cookies=self.cookies)
            
            response = await self.client.get(teams_url)
            self._log_response(response)
            response.raise_for_status()

            # Parse team standings from the page
            logger.debug(f"Parsing team standings from HTML (content length: {len(response.text)})")
            standings = self._parse_team_standings_from_html(response.text)

            # Save standings to database
            if standings:
                self.database.save_team_standings(standings)

            # Record the request
            self.rate_limiter.record_request("teams")

            logger.debug(f"Successfully fetched {len(standings)} team standings")
            return standings

        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching team standings: {e}")
            # Try to get response from the exception
            try:
                response = getattr(e, 'response', None)
                if response:
                    self._log_response(response)
            except Exception:
                pass
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching team standings: {e}")
            return []

    def _parse_team_standings_from_html(self, html: str) -> list[TeamStanding]:
        """Parse team standings from HTML content."""
        soup = BeautifulSoup(html, "html.parser")
        standings = []

        # Look for the progress bar that contains team standings
        progress_div = soup.find("div", class_="progress")
        if not progress_div or not isinstance(progress_div, Tag):
            logger.warning("No progress bar found for team standings")
            logger.warning(f"HTML: {html}")
            return standings

        # Find all progress bars within the main progress div
        progress_bars = progress_div.find_all("div", class_="progress-bar")
        if not progress_bars or len(progress_bars) != 2:
            logger.warning(f"Expected 2 progress bars, found {len(progress_bars) if progress_bars else 0}")
            return standings

        logger.debug(f"Found {len(progress_bars)} progress bars for team standings")

        # Use team colors to determine which bar corresponds to which team
        team1_percentage = self._parse_team_percentage_by_color(progress_bars)
        if team1_percentage is not None:
            fetched_at = datetime.now()
            
            standing = TeamStanding(
                team1_percentage=team1_percentage,
                fetched_at=fetched_at,
                leader_change=False  # Will be set by database logic
            )
            standings.append(standing)
            logger.debug(f"Parsed team standings: Team 1 = {team1_percentage:.2f}%, Team 2 = {100-team1_percentage:.2f}%")

        return standings

    def _parse_team_percentage_by_color(self, progress_bars) -> float | None:
        """Parse team percentage using team colors to determine which bar is which team."""
        try:
            if not settings.teams:
                logger.warning("No team colors configured, falling back to first bar as team1")
                return self._parse_team1_percentage(progress_bars[0])
            
            team1_color = settings.teams.team1.color
            team2_color = settings.teams.team2.color
            
            logger.debug(f"Looking for team colors: Team1={team1_color}, Team2={team2_color}")
            
            team1_percentage = None
            team2_percentage = None
            
            for bar in progress_bars:
                bg_color = self._extract_background_color(bar)
                if not bg_color:
                    continue
                
                width_percent = self._extract_width_percentage(bar)
                if width_percent is None:
                    continue
                
                # Match color to team
                if bg_color.lower() == team1_color.lower():
                    team1_percentage = width_percent
                    logger.debug(f"Team1 ({settings.teams.team1.name}) percentage: {width_percent:.2f}%")
                elif bg_color.lower() == team2_color.lower():
                    team2_percentage = width_percent
                    logger.debug(f"Team2 ({settings.teams.team2.name}) percentage: {width_percent:.2f}%")
                else:
                    logger.warning(f"Unknown team color: {bg_color}")
            
            # Return team1 percentage (the one we store in the database)
            if team1_percentage is not None:
                return team1_percentage
            elif team2_percentage is not None:
                # If we only found team2, calculate team1 percentage
                return 100 - team2_percentage
            
            logger.warning("Could not determine team percentages from colors")
            return None

        except Exception as e:
            logger.error(f"Error parsing team percentage by color: {e}")
            return None

    def _extract_background_color(self, bar_element) -> str | None:
        """Extract background color from a progress bar element."""
        style = bar_element.get("style", "")
        if "background-color:" not in style:
            return None
        
        # Parse the style attribute
        style_parts = style.split(";")
        for part in style_parts:
            if "background-color:" in part:
                bg_color = part.split(":")[1].strip()
                logger.debug(f"Found background color: {bg_color}")
                return bg_color
        
        return None

    def _extract_width_percentage(self, bar_element) -> float | None:
        """Extract width percentage from a progress bar element."""
        try:
            # Get the style attribute
            style = bar_element.get("style", "")
            
            # Parse style for width
            style_parts = style.split(";")
            for part in style_parts:
                if "width:" in part:
                    width_part = part.split(":")[1].strip()
                    if "%" in width_part:
                        width_percent = float(width_part.replace("%", ""))
                        logger.debug(f"Using width percentage: {width_percent:.4f}%")
                        return width_percent
            
            return None

        except Exception as e:
            logger.error(f"Error extracting width percentage: {e}")
            return None

    def _parse_team1_percentage(self, bar_element) -> float | None:
        """Parse team1 percentage from the first progress bar element."""
        try:
            # Extract the style attribute to get width
            style_attr = bar_element.get("style", "")
            logger.debug(f"Parsing team1 progress bar with style: {style_attr}")
            
            # Extract width percentage
            width_match = re.search(r"width:([\d.]+)%", style_attr)
            if not width_match:
                logger.warning("No width found in progress bar style")
                return None
            
            width_percent = float(width_match.group(1))
            
            # Extract percentage text from the bar content as backup
            percentage_text = bar_element.get_text(strip=True)
            percentage_match = re.search(r"([\d.]+)%", percentage_text)
            if percentage_match:
                percentage = float(percentage_match.group(1))
                # Use the text percentage if it's close to the width percentage
                if abs(percentage - width_percent) < 1.0:
                    return percentage
            
            # Return width percentage as fallback
            return width_percent

        except Exception as e:
            logger.error(f"Error parsing team1 percentage: {e}")
            return None

    async def close(self) -> None:
        """Close the HTTP client."""
        logger.debug("Closing ArtFight client")
        await self.client.aclose()
        logger.debug("ArtFight client closed")
