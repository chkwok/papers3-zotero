#!/usr/bin/env python3
"""
Analyze Papers3 collection hierarchy and show tree structure with item counts
"""

import json
from pathlib import Path
from typing import Dict, List, Any

def print_collection_tree(papers3_path='.'):
    """Print the Papers3 collection hierarchy as a tree with item counts"""
    
    catalog_path = Path(papers3_path) / 'catalog'
    
    # Load collections
    coll_file = catalog_path / 'papers3_collections.json'
    if not coll_file.exists():
        print(f"Error: Collections file not found at {coll_file}")
        return
    
    with open(coll_file, 'r', encoding='utf-8') as f:
        coll_data = json.load(f)
    
    # Load publications to get collection assignments
    pub_file = catalog_path / 'papers3_publications_full.json'
    if not pub_file.exists():
        pub_file = catalog_path / 'papers3_publications.json'
    
    # Build item count map
    item_counts = {}
    if pub_file.exists():
        with open(pub_file, 'r', encoding='utf-8') as f:
            pub_data = json.load(f)
        
        # Count items per collection UUID
        for pub in pub_data['publications']:
            if pub.get('collections'):
                for coll in pub['collections']:
                    if isinstance(coll, dict):
                        coll_uuid = coll.get('collection_uuid')
                    else:
                        coll_uuid = str(coll)
                    
                    if coll_uuid:
                        item_counts[coll_uuid] = item_counts.get(coll_uuid, 0) + 1
    
    def print_tree(collection: Dict, level: int = 0, prefix: str = "", is_last: bool = True):
        """Recursively print collection tree"""
        # Tree symbols
        if level == 0:
            tree_prefix = ""
            connector = ""
        else:
            connector = "└── " if is_last else "├── "
            tree_prefix = prefix
        
        # Get item count
        coll_uuid = collection.get('uuid', '')
        item_count = item_counts.get(coll_uuid, 0)
        
        # Get publications list if available
        pub_count = len(collection.get('publications', []))
        
        # Print collection name with counts
        name = collection.get('name', 'Unknown')
        children = collection.get('children', [])
        
        # Format the output
        if children:
            # Has children - show both counts
            print(f"{tree_prefix}{connector}📁 {name} ({len(children)} subfolders, {item_count} items)")
        else:
            # Leaf node - highlight and show item count
            if item_count > 0:
                print(f"{tree_prefix}{connector}📄 {name} [{item_count} items] ★")
            else:
                print(f"{tree_prefix}{connector}📄 {name} [empty]")
        
        # Update prefix for children
        if level > 0:
            extension = "    " if is_last else "│   "
            new_prefix = prefix + extension
        else:
            new_prefix = ""
        
        # Print children
        for i, child in enumerate(children):
            is_last_child = (i == len(children) - 1)
            print_tree(child, level + 1, new_prefix, is_last_child)
    
    # Print header
    print("\n" + "="*60)
    print("PAPERS3 COLLECTION HIERARCHY")
    print("="*60)
    print("📁 = Has subfolders  📄 = Leaf collection  ★ = Has items\n")
    
    # Print statistics
    def count_stats(collections):
        total = len(collections)
        leaves = 0
        with_items = 0
        max_depth = 0
        
        def analyze(coll, depth=0):
            nonlocal leaves, with_items, max_depth
            max_depth = max(max_depth, depth)
            children = coll.get('children', [])
            if not children:
                leaves += 1
                if item_counts.get(coll.get('uuid', ''), 0) > 0:
                    with_items += 1
            for child in children:
                analyze(child, depth + 1)
        
        for coll in collections:
            analyze(coll)
        
        return total, leaves, with_items, max_depth
    
    # Calculate and print statistics
    total_colls = 0
    leaf_colls = 0
    populated_leaves = 0
    max_depth = 0
    
    for coll in coll_data['collections']:
        stats = count_stats([coll])
        total_colls += stats[0]
        leaf_colls += stats[1]
        populated_leaves += stats[2]
        max_depth = max(max_depth, stats[3])
    
    print(f"Total collections: {total_colls}")
    print(f"Leaf collections: {leaf_colls}")
    print(f"Populated leaves: {populated_leaves}")
    print(f"Maximum depth: {max_depth} levels")
    print(f"Total items in collections: {sum(item_counts.values())}")
    print("\n" + "="*60 + "\n")
    
    # Print the tree
    for i, collection in enumerate(coll_data['collections']):
        is_last = (i == len(coll_data['collections']) - 1)
        print_tree(collection, 0, "", is_last)
        if not is_last:
            print()  # Space between root collections
    
    # Print leaf collections with most items
    print("\n" + "="*60)
    print("TOP POPULATED LEAF COLLECTIONS")
    print("="*60)
    
    # Find all leaf collections with items
    leaf_items = []
    
    def find_leaves(coll):
        if not coll.get('children'):
            coll_uuid = coll.get('uuid', '')
            count = item_counts.get(coll_uuid, 0)
            if count > 0:
                leaf_items.append((coll.get('name', 'Unknown'), count))
        else:
            for child in coll.get('children', []):
                find_leaves(child)
    
    for coll in coll_data['collections']:
        find_leaves(coll)
    
    # Sort by item count and show top 20
    leaf_items.sort(key=lambda x: x[1], reverse=True)
    for name, count in leaf_items[:20]:
        print(f"  {count:4} items - {name}")
    
    if len(leaf_items) > 20:
        print(f"  ... and {len(leaf_items) - 20} more populated collections")
    
    print("="*60 + "\n")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Analyze Papers3 collection hierarchy')
    parser.add_argument('--papers3-path', default='.', help='Path to Papers3 export directory')
    args = parser.parse_args()
    
    print_collection_tree(args.papers3_path)