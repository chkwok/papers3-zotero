# Zotero Database Direct Import Mapping

## Zotero Database Structure Analysis

### Core Tables

1. **libraries** - Single row for user library (libraryID=1)
2. **items** - All items (articles, books, attachments, notes)
   - itemID: Primary key
   - itemTypeID: References itemTypes table
   - libraryID: Always 1 for local library
   - key: Unique 8-character key (e.g., "ABCD1234")
   - dateAdded/dateModified: Timestamps

3. **collections** - Folder hierarchy
   - collectionID: Primary key
   - collectionName: Display name
   - parentCollectionID: NULL for root, ID for children
   - key: Unique 8-character key

4. **collectionItems** - Maps items to collections
   - Many-to-many relationship
   - Items can be in multiple collections

5. **itemData** - Field values for items
   - Uses fieldID → valueID pattern
   - Values stored in itemDataValues table

6. **itemAttachments** - PDF and file attachments
   - linkMode: 0=imported file, 2=linked file
   - path: Relative path for imported, absolute for linked
   - parentItemID: Links to parent item

7. **creators** - Author/editor records
   - firstName, lastName, fieldMode
   - Deduplicated across items

8. **itemCreators** - Links creators to items
   - orderIndex: Preserves author order
   - creatorTypeID: 8=author, 10=editor, 11=translator

9. **tags** - Keywords/tags
   - Simple name-based deduplication

10. **itemTags** - Links tags to items

## Papers3 to Zotero Mapping

### Item Type Mapping

| Papers3 Type | Papers3 Code | Zotero itemTypeID | Zotero typeName |
|-------------|--------------|-------------------|-----------------|
| Article | 400 | 22 | journalArticle |
| Periodical | -100 | 22 | journalArticle (as container) |
| Book | 0 | 7 | book |
| Book Chapter | 1 | 8 | bookSection |
| Report | 700 | 34 | report |
| Patent | 500 | 29 | patent |
| Thesis | 10 | 37 | thesis |
| Media | 300 | 14 | document |
| Conference | -200 | 11 | conferencePaper |
| Website | -300 | 40 | webpage |
| Manual | -1000 | 14 | document |

### Field Mapping

| Papers3 Field | Zotero fieldID | Zotero fieldName | Notes |
|--------------|----------------|------------------|-------|
| title | 1 | title | Direct |
| subtitle | - | - | Append to title with ": " |
| author_string | - | - | Parse to creators |
| publication_date | 6 | date | Format: YYYY-MM-DD |
| doi | 59 | DOI | Direct |
| publisher | varies | publisher | Direct |
| volume | 19 | volume | Direct |
| number | 76 | issue | Direct |
| startpage/endpage | 32 | pages | Format: "123-456" |
| abstract/summary | 2 | abstractNote | Direct |
| notes | - | itemNotes | Separate table |
| keyword_string | - | tags | Parse to tags |
| bundle | varies | publicationTitle | For articles |
| rating | 16 | extra | Add as "Rating: 4" |
| read_status | 16 | extra | Add as "Read Status: read" |
| flagged | - | tag | Add "Flagged" tag |
| url | 13 | url | Direct |

### Creator Handling

Papers3 OrderedAuthor → Zotero itemCreators:
```sql
-- Papers3 author types
0 → creatorTypeID 8 (author)
1 → creatorTypeID 10 (editor)
2 → creatorTypeID 8 (author) -- photographer
3 → creatorTypeID 11 (translator)
```

### Collection Hierarchy

Papers3 Collection → Zotero collections:
1. Create root collections first (parent=NULL)
2. Create child collections with parentCollectionID
3. Map Papers3 UUID to Zotero collectionID
4. Link items via collectionItems table

### PDF Attachment Strategy

Papers3 PDF → Zotero itemAttachments:

**Option 1: Linked Files (Recommended)**
- linkMode = 2 (LINK_MODE_LINKED_FILE)
- Store absolute path to existing PDF
- No file copying needed
- Preserves Papers3 file organization

**Option 2: Imported Files**
- linkMode = 0 (LINK_MODE_IMPORTED_FILE)
- Copy PDFs to Zotero storage folder
- Path format: "storage:{key}/{filename}"
- Requires creating storage directories

### Bundle Relationships

Papers3 bundles (journal → articles):
- Use itemRelations table
- Or store journal info in publicationTitle field
- Consider using "related" items feature

## Implementation Steps

### 1. Prepare Zotero Database

```sql
-- Start with clean database
-- libraryID = 1 already exists

-- Generate keys for items
-- Format: 8 random alphanumeric characters
```

### 2. Import Collections First

```python
def import_collections(papers3_collections):
    collection_map = {}
    
    # Sort by hierarchy level (root first)
    for p3_collection in sorted_by_hierarchy(papers3_collections):
        parent_id = None
        if p3_collection['parent']:
            parent_id = collection_map[p3_collection['parent']]
        
        # Insert into Zotero
        cursor.execute("""
            INSERT INTO collections 
            (collectionName, parentCollectionID, libraryID, key)
            VALUES (?, ?, 1, ?)
        """, (p3_collection['name'], parent_id, generate_key()))
        
        collection_map[p3_collection['uuid']] = cursor.lastrowid
    
    return collection_map
```

### 3. Import Publications

```python
def import_publication(p3_pub):
    # Map item type
    item_type_id = map_item_type(p3_pub['type'])
    
    # Create item
    cursor.execute("""
        INSERT INTO items 
        (itemTypeID, libraryID, key, dateAdded, dateModified)
        VALUES (?, 1, ?, ?, ?)
    """, (item_type_id, generate_key(), 
          p3_pub['created_at'], p3_pub['updated_at']))
    
    item_id = cursor.lastrowid
    
    # Add field data
    add_field_data(item_id, p3_pub)
    
    # Add creators
    add_creators(item_id, p3_pub['authors'])
    
    # Add tags
    add_tags(item_id, p3_pub['keywords'])
    
    # Add to collections
    add_to_collections(item_id, p3_pub['collections'])
    
    return item_id
```

### 4. Import PDFs as Attachments

```python
def add_pdf_attachment(parent_item_id, pdf_data):
    # Create attachment item
    cursor.execute("""
        INSERT INTO items 
        (itemTypeID, libraryID, key, dateAdded)
        VALUES (3, 1, ?, CURRENT_TIMESTAMP)
    """, (generate_key(),))
    
    attachment_id = cursor.lastrowid
    
    # Add attachment details
    cursor.execute("""
        INSERT INTO itemAttachments
        (itemID, parentItemID, linkMode, contentType, path)
        VALUES (?, ?, 2, 'application/pdf', ?)
    """, (attachment_id, parent_item_id, pdf_data['path']))
    
    # Add title
    add_field_value(attachment_id, 1, pdf_data['caption'])
```

### 5. Handle Special Fields

Store Papers3-specific metadata in Extra field:
```
Rating: 4/5
Read Status: Read
Times Cited: 42
Times Read: 3
Papers3 UUID: {original-uuid}
```

## Key Generation

```python
import random
import string

def generate_key(length=8):
    """Generate Zotero-style key"""
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))
```

## Data Validation

Before import:
1. Check for duplicate DOIs
2. Validate dates (convert invalid to NULL)
3. Ensure author names are parseable
4. Verify PDF paths exist
5. Check collection hierarchy integrity

## Transaction Management

```python
conn = sqlite3.connect('zotero.sqlite')
conn.execute('BEGIN TRANSACTION')

try:
    # All imports here
    import_collections()
    import_publications()
    import_attachments()
    
    conn.commit()
except Exception as e:
    conn.rollback()
    raise
```

## Post-Import Tasks

1. Update item counts in collections
2. Rebuild search indexes
3. Verify foreign key constraints
4. Check for orphaned attachments
5. Generate citation keys if needed

## Limitations

### Cannot Preserve
- Exact Papers3 UUIDs (use Extra field)
- Bundle relationships perfectly (use related items)
- View settings and UI preferences
- Change history/sync data

### Partially Preserved
- Ratings (as text in Extra)
- Read status (as text in Extra)
- Color labels (as tags)
- Multiple PDFs per item (flattened)

## Testing Strategy

1. Start with 10-item test import
2. Verify in Zotero UI
3. Check all relationships
4. Test PDF opening
5. Validate search/sort
6. Scale to full import

## Error Handling

Log all:
- Unmapped item types
- Invalid dates
- Missing PDFs
- Failed creator parsing
- Collection hierarchy issues

Create fallback for each error type.