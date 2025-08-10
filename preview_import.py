#!/usr/bin/env python3
"""
Preview what will be imported from Papers3 to Zotero
"""

import json
from pathlib import Path
from collections import Counter

def preview_papers3_data(papers3_path='.'):
    """Show statistics about Papers3 data that will be imported"""
    
    catalog_path = Path(papers3_path) / 'catalog'
    
    print("\n" + "="*60)
    print("PAPERS3 TO ZOTERO IMPORT PREVIEW")
    print("="*60)
    
    # Load publications
    pub_file = catalog_path / 'papers3_publications_full.json'
    if not pub_file.exists():
        pub_file = catalog_path / 'papers3_publications.json'
    
    if not pub_file.exists():
        print(f"Error: No publications file found in {catalog_path}")
        return
    
    with open(pub_file, 'r', encoding='utf-8') as f:
        pub_data = json.load(f)
    
    publications = pub_data['publications']
    print(f"\n📚 PUBLICATIONS: {len(publications):,} items")
    
    # Type distribution
    type_counts = Counter(p.get('type', 'unknown') for p in publications)
    print("\n  Type Distribution:")
    for pub_type, count in type_counts.most_common():
        percentage = (count / len(publications)) * 100
        print(f"    • {pub_type}: {count:,} ({percentage:.1f}%)")
    
    # Year distribution
    years = []
    for p in publications:
        date = p.get('publication_date')
        if date and len(date) >= 4:
            try:
                year = int(date[:4])
                if 1900 <= year <= 2030:
                    years.append(year)
            except:
                pass
    
    if years:
        print(f"\n  Year Range: {min(years)} - {max(years)}")
        recent = sum(1 for y in years if y >= 2020)
        print(f"  Recent (2020+): {recent:,} items")
    
    # Metadata completeness
    with_doi = sum(1 for p in publications if p.get('doi'))
    with_abstract = sum(1 for p in publications if p.get('summary') or p.get('notes'))
    with_authors = sum(1 for p in publications if p.get('authors'))
    
    print("\n  Metadata Completeness:")
    print(f"    • With DOI: {with_doi:,} ({with_doi/len(publications)*100:.1f}%)")
    print(f"    • With Abstract: {with_abstract:,} ({with_abstract/len(publications)*100:.1f}%)")
    print(f"    • With Authors: {with_authors:,} ({with_authors/len(publications)*100:.1f}%)")
    
    # Collections
    coll_file = catalog_path / 'papers3_collections.json'
    if coll_file.exists():
        with open(coll_file, 'r', encoding='utf-8') as f:
            coll_data = json.load(f)
        
        def count_collections(collections):
            count = len(collections)
            for c in collections:
                count += count_collections(c.get('children', []))
            return count
        
        total_collections = count_collections(coll_data['collections'])
        print(f"\n📁 COLLECTIONS: {total_collections:,} folders")
        
        # Show top-level collections
        print("\n  Top-level folders:")
        for coll in coll_data['collections'][:10]:
            child_count = len(coll.get('children', []))
            print(f"    • {coll['name']} ({child_count} subfolders)")
        if len(coll_data['collections']) > 10:
            print(f"    ... and {len(coll_data['collections']) - 10} more")
    
    # Tags/Keywords
    all_keywords = []
    for p in publications:
        if p.get('keywords'):
            for kw in p['keywords']:
                if isinstance(kw, dict):
                    all_keywords.append(kw.get('name', ''))
                else:
                    all_keywords.append(str(kw))
    
    unique_keywords = set(k for k in all_keywords if k)
    print(f"\n🏷️  TAGS: {len(unique_keywords):,} unique tags")
    
    keyword_counts = Counter(all_keywords)
    print("\n  Most common tags:")
    for tag, count in keyword_counts.most_common(10):
        if tag:
            print(f"    • {tag}: {count} uses")
    
    # PDFs
    pdf_count = sum(len(p.get('pdfs', [])) for p in publications)
    items_with_pdfs = sum(1 for p in publications if p.get('pdfs'))
    
    print(f"\n📎 ATTACHMENTS: {pdf_count:,} PDFs")
    print(f"  Items with PDFs: {items_with_pdfs:,} ({items_with_pdfs/len(publications)*100:.1f}%)")
    print("  ⚠️  Note: Use --skip-attachments flag if PDFs not available locally")
    
    # Special metadata
    with_rating = sum(1 for p in publications if p.get('rating'))
    flagged = sum(1 for p in publications if p.get('flagged'))
    
    print(f"\n⭐ SPECIAL METADATA:")
    print(f"  Items with ratings: {with_rating:,}")
    print(f"  Flagged items: {flagged:,}")
    print("  (Will be preserved in Zotero's Extra field)")
    
    # Import estimate
    print("\n" + "="*60)
    print("IMPORT SUMMARY")
    print("="*60)
    print(f"\nThis will create in Zotero:")
    print(f"  • {len(publications):,} publication items")
    print(f"  • {total_collections if 'total_collections' in locals() else '?'} collections")
    print(f"  • {len(unique_keywords):,} tags")
    print(f"  • {pdf_count:,} PDF attachments (if not skipped)")
    
    # Size estimate
    avg_item_size = 2  # KB per item (rough estimate)
    estimated_size = (len(publications) * avg_item_size) / 1024
    print(f"\nEstimated database size increase: ~{estimated_size:.1f} MB")
    
    print("\n" + "="*60)
    print("\nTo import everything:")
    print("  uv run python papers3_to_zotero.py --skip-attachments")
    print("\nTo test with a small sample first:")
    print("  uv run python papers3_to_zotero.py --test --limit 10 --skip-attachments")
    print("="*60 + "\n")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Preview Papers3 to Zotero import')
    parser.add_argument('--papers3-path', default='.', help='Path to Papers3 export directory')
    args = parser.parse_args()
    
    preview_papers3_data(args.papers3_path)