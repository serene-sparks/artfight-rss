#!/usr/bin/env python3
"""Test script to verify revision detection logic only triggers for meaningful changes."""

from artfight_feed.database import ArtFightDatabase
from artfight_feed.models import ArtFightNews
from pathlib import Path
from datetime import datetime, UTC
import html2text

def test_revision_detection():
    """Test that revisions are only detected for title/content changes, not time/editor changes."""
    print("🧪 Testing Revision Detection Logic")
    print("=" * 60)
    
    # Create test database
    test_db_path = Path("test_revision_logic.db")
    database = ArtFightDatabase(test_db_path)
    
    try:
        # Test case 1: Title change only
        print("\n📝 Test Case 1: Title Change Only")
        print("-" * 40)
        
        old_post = ArtFightNews(
            id=1,
            title="Original Title",
            content="<p>Same content</p>",
            author="admin",
            posted_at=datetime.now(UTC),
            edited_at=datetime.now(UTC),
            edited_by="admin",
            url="https://artfight.net/news/1",
            fetched_at=datetime.now(UTC)
        )
        
        new_post = ArtFightNews(
            id=1,
            title="Updated Title",
            content="<p>Same content</p>",
            author="admin",
            posted_at=datetime.now(UTC),
            edited_at=datetime.now(UTC),
            edited_by="sunnyshrimp",
            url="https://artfight.net/news/1",
            fetched_at=datetime.now(UTC)
        )
        
        # Save old post first
        database.save_news([old_post])
        
        # Now save the revised post
        results = database.save_news([new_post])
        current_post, old_post_revision = results[0]
        
        if old_post_revision:
            print("✅ Revision detected for title change")
        else:
            print("❌ No revision detected for title change")
        
        # Test case 2: Content change only
        print("\n📝 Test Case 2: Content Change Only")
        print("-" * 40)
        
        old_post2 = ArtFightNews(
            id=2,
            title="Same Title",
            content="<p>Original content</p>",
            author="admin",
            posted_at=datetime.now(UTC),
            edited_at=datetime.now(UTC),
            edited_by="admin",
            url="https://artfight.net/news/2",
            fetched_at=datetime.now(UTC)
        )
        
        new_post2 = ArtFightNews(
            id=2,
            title="Same Title",
            content="<div>Updated content</div>",
            author="admin",
            posted_at=datetime.now(UTC),
            edited_at=datetime.now(UTC),
            edited_by="sunnyshrimp",
            url="https://artfight.net/news/2",
            fetched_at=datetime.now(UTC)
        )
        
        # Save old post first
        database.save_news([old_post2])
        
        # Now save the revised post
        results2 = database.save_news([new_post2])
        current_post2, old_post_revision2 = results2[0]
        
        if old_post_revision2:
            print("✅ Revision detected for content change")
        else:
            print("❌ No revision detected for content change")
        
        # Test case 3: Only time/editor changes (should NOT trigger revision)
        print("\n📝 Test Case 3: Only Time/Editor Changes (Should NOT Trigger Revision)")
        print("-" * 40)
        
        old_post3 = ArtFightNews(
            id=3,
            title="Same Title",
            content="<p>Same content</p>",
            author="admin",
            posted_at=datetime.now(UTC),
            edited_at=datetime.now(UTC),
            edited_by="admin",
            url="https://artfight.net/news/3",
            fetched_at=datetime.now(UTC)
        )
        
        new_post3 = ArtFightNews(
            id=3,
            title="Same Title",
            content="<p>Same content</p>",
            author="admin",
            posted_at=datetime.now(UTC),
            edited_at=datetime.now(UTC),
            edited_by="sunnyshrimp",  # Only editor changed
            url="https://artfight.net/news/3",
            fetched_at=datetime.now(UTC)
        )
        
        # Save old post first
        database.save_news([old_post3])
        
        # Now save the revised post
        results3 = database.save_news([new_post3])
        current_post3, old_post_revision3 = results3[0]
        
        if old_post_revision3:
            print("❌ Revision detected when only editor changed (should not happen)")
        else:
            print("✅ No revision detected for editor-only change (correct behavior)")
        
        # Test case 4: HTML structure change but same markdown content
        print("\n📝 Test Case 4: HTML Structure Change but Same Markdown Content")
        print("-" * 40)
        
        old_post4 = ArtFightNews(
            id=4,
            title="Same Title",
            content="<p>This is <strong>bold</strong> text</p>",
            author="admin",
            posted_at=datetime.now(UTC),
            edited_at=datetime.now(UTC),
            edited_by="admin",
            url="https://artfight.net/news/4",
            fetched_at=datetime.now(UTC)
        )
        
        new_post4 = ArtFightNews(
            id=4,
            title="Same Title",
            content="<div>This is <b>bold</b> text</div>",
            author="admin",
            posted_at=datetime.now(UTC),
            edited_at=datetime.now(UTC),
            edited_by="sunnyshrimp",
            url="https://artfight.net/news/4",
            fetched_at=datetime.now(UTC)
        )
        
        # Save old post first
        database.save_news([old_post4])
        
        # Now save the revised post
        results4 = database.save_news([new_post4])
        current_post4, old_post_revision4 = results4[0]
        
        if old_post_revision4:
            print("❌ Revision detected for HTML structure change (should not happen)")
        else:
            print("✅ No revision detected for HTML structure change (correct behavior)")
        
        print("\n✅ Revision detection logic test completed!")
        
    finally:
        # Cleanup
        if test_db_path.exists():
            test_db_path.unlink()
            print("✅ Test database cleaned up")

if __name__ == "__main__":
    test_revision_detection()
