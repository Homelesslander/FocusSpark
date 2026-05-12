#!/usr/bin/env python3
"""
Database diagnostic script for PythonAnywhere
Run this to check parent-child links and task card ownership
"""

import sqlite3
import sys
import os

def diagnose_database():
    db_path = 'adhd_app.db'
    
    if not os.path.exists(db_path):
        print(f"❌ Database file not found: {db_path}")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.row_factory = sqlite3.Row
        
        print("🔍 DATABASE DIAGNOSTIC REPORT")
        print("=" * 50)
        
        # 1. Check all users and their parent links
        print("\n📋 USERS & PARENT LINKS:")
        c.execute("SELECT username, role, parent_username FROM users ORDER BY username")
        users = c.fetchall()
        
        if not users:
            print("❌ No users found in database")
        else:
            for user in users:
                parent_status = f"→ Parent: {user['parent_username']}" if user['parent_username'] else "→ No parent linked"
                print(f"👤 {user['username']} ({user['role']}) {parent_status}")
        
        # 2. Check all task cards and ownership
        print("\n📴 TASK CARDS & OWNERSHIP:")
        c.execute("SELECT id, title, parent_username, is_recommended, created_at FROM visual_task_cards ORDER BY created_at DESC")
        cards = c.fetchall()
        
        if not cards:
            print("❌ No task cards found in database")
        else:
            for card in cards:
                card_type = "🎯 Recommended" if card['is_recommended'] else "👨‍👩‍👧‍👦 Custom"
                print(f"{card_type} Card #{card['id']}: '{card['title']}' by {card['parent_username']}")
        
        # 3. Check task completions
        print("\n✅ TASK COMPLETIONS:")
        c.execute("SELECT card_id, child_username, completed_at FROM task_completions ORDER BY completed_at DESC")
        completions = c.fetchall()
        
        if not completions:
            print("❌ No task completions found")
        else:
            for comp in completions:
                print(f"🎉 Card #{comp['card_id']} completed by {comp['child_username']} at {comp['completed_at']}")
        
        # 4. Verify parent-child card access
        print("\n🔗 PARENT-CHILD CARD ACCESS:")
        for user in users:
            if user['role'] == 'child' and user['parent_username']:
                # Check what cards this child should see
                c.execute("""
                    SELECT id, title FROM visual_task_cards 
                    WHERE parent_username = ? AND is_recommended = 0
                """, (user['parent_username'],))
                child_cards = c.fetchall()
                print(f"👶 {user['username']} should see {len(child_cards)} cards from parent {user['parent_username']}")
                for card in child_cards:
                    print(f"   → Card #{card['id']}: '{card['title']}'")
        
        # 5. Check for any data inconsistencies
        print("\n⚠️  DATA CONSISTENCY CHECKS:")
        
        # Check orphaned cards (cards with non-existent parents)
        c.execute("SELECT DISTINCT parent_username FROM visual_task_cards WHERE parent_username IS NOT NULL")
        card_parents = [row[0] for row in c.fetchall()]
        user_usernames = [user['username'] for user in users]
        
        orphaned_parents = set(card_parents) - set(user_usernames)
        if orphaned_parents:
            print(f"❌ Orphaned cards from non-existent parents: {orphaned_parents}")
        else:
            print("✅ All card owners exist as users")
        
        # Check children linked to non-existent parents
        child_parents = [user['parent_username'] for user in users if user['parent_username']]
        missing_parents = set(child_parents) - set(user_usernames)
        if missing_parents:
            print(f"❌ Children linked to non-existent parents: {missing_parents}")
        else:
            print("✅ All child parent links are valid")
        
        conn.close()
        print("\n🎯 DIAGNOSTIC COMPLETE")
        
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

if __name__ == "__main__":
    diagnose_database()
