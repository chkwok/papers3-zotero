# Zotero Import Research

## Import Method Options

### 1. **Zotero Web API (Recommended for Large Libraries)**

**Pros:**
- Can handle 50 items per request
- Full control over metadata mapping
- Preserves relationships (collections, tags, attachments)
- Can upload PDFs programmatically
- Python library available (pyzotero)

**Cons:**
- Requires API key setup
- Rate limits apply
- More complex implementation
- Need to handle versioning

**Implementation:**
```python
# Using pyzotero
from pyzotero import zotero
zot = zotero.Zotero(library_id, 'user', api_key)

# Create items in batches of 50
items_batch = []  # List of item dicts
response = zot.create_items(items_batch)
```

### 2. **RIS Format Import**

**Pros:**
- Well-established format
- Zotero has robust RIS importer
- Single file import possible
- Preserves most metadata

**Cons:**
- Limited to RIS field mappings
- Collections must be recreated manually
- PDF paths not preserved
- Tags may be limited

**Format Example:**
```
TY  - JOUR
AU  - Author, First
AU  - Author, Second
TI  - Article Title
JO  - Journal Name
VL  - 10
IS  - 2
SP  - 100
EP  - 120
PY  - 2024
DO  - 10.1234/doi
ER  -
```

### 3. **BibTeX Import**

**Pros:**
- Simple text format
- Better BibTeX plugin for enhanced features
- Good for LaTeX users
- Preserves citation keys

**Cons:**
- Limited metadata fields
- Author parsing can be problematic
- No collection hierarchy
- PDF attachment issues

### 4. **CSL JSON Import**

**Pros:**
- Native Zotero format
- Preserves all metadata
- Supports all item types
- Clean JSON structure

**Cons:**
- Must match CSL schema exactly
- No bulk import UI
- Collections separate

**Format Example:**
```json
[
  {
    "id": "item1",
    "type": "article-journal",
    "title": "Title",
    "author": [
      {"family": "Doe", "given": "John"}
    ],
    "issued": {"date-parts": [[2024]]},
    "container-title": "Journal",
    "DOI": "10.1234/doi"
  }
]
```

### 5. **Direct SQLite Database Manipulation (Not Recommended)**

**Pros:**
- Fastest for huge libraries
- Complete control

**Cons:**
- Risk of database corruption
- Undocumented schema changes
- No official support
- Sync issues

## Recommended Approach for Papers3 Data

### Phase 1: API Setup
1. Install Zotero and create account
2. Generate API key at zotero.org/settings/keys
3. Get library ID from settings
4. Install pyzotero: `pip install pyzotero`

### Phase 2: Data Mapping

Create mapping from Papers3 to Zotero fields:

| Papers3 Field | Zotero Field | Notes |
|--------------|--------------|--------|
| uuid | key | Generate new or use as extra field |
| title | title | Direct mapping |
| author_string | creators | Parse into firstName/lastName |
| publication_date | date | Convert from ISO to Zotero format |
| doi | DOI | Direct mapping |
| type/subtype | itemType | Need type conversion table |
| bundle | publicationTitle | For articles |
| collections | collections | Create hierarchy first |
| keywords | tags | Direct as array |
| pdfs | attachments | Need file path handling |

### Phase 3: Implementation Strategy

```python
# Pseudo-code structure
def convert_papers3_to_zotero():
    # 1. Load Papers3 JSON
    papers3_data = load_json('papers3_publications_full.json')
    
    # 2. Create collections first
    collections_map = create_collections_hierarchy()
    
    # 3. Process in batches
    for batch in chunks(papers3_data['publications'], 50):
        zotero_items = []
        for paper in batch:
            item = map_to_zotero_format(paper)
            zotero_items.append(item)
        
        # 4. Upload batch
        response = zot.create_items(zotero_items)
        
        # 5. Add PDFs as attachments
        for item_key, pdf_path in pdf_mappings:
            upload_pdf(item_key, pdf_path)
```

## Testing Strategy

### Small Test Import
1. Extract 10 diverse items from Papers3
2. Include different types (article, book, report)
3. Test with PDFs, collections, tags
4. Verify all metadata preserved

### Validation Checklist
- [ ] Authors in correct order
- [ ] Dates properly formatted
- [ ] DOIs functional
- [ ] PDFs attached and readable
- [ ] Collections hierarchy preserved
- [ ] Tags imported
- [ ] Unicode characters handled
- [ ] Bundle relationships (journal-article)

## Known Challenges

### 1. Author Parsing
Papers3 stores full names; Zotero needs firstName/lastName split.
Solution: Use name parsing library or Papers3 author table.

### 2. PDF File Paths
Papers3 uses relative paths; Zotero needs absolute or upload.
Solution: Reconstruct full paths or upload via API.

### 3. Collection Hierarchy
Must create parent collections before children.
Solution: Sort by hierarchy level, create in order.

### 4. Date Formats
Papers3 uses ISO; Zotero uses various formats by type.
Solution: Parse and reformat based on item type.

### 5. Item Type Mapping
Papers3 has different type taxonomy than Zotero.
Solution: Create comprehensive mapping table.

## Next Steps

1. **Create Type Mapping Table**
   - Map all Papers3 types to Zotero itemTypes
   - Document any fields that won't transfer

2. **Write Conversion Script**
   - Start with single item converter
   - Add batch processing
   - Include error handling

3. **Test with Sample Data**
   - Use 10-item test set
   - Verify in Zotero desktop
   - Check sync to web library

4. **Scale to Full Import**
   - Process in 50-item batches
   - Monitor API rate limits
   - Log any failures for retry

## Resources

- [Zotero Web API Documentation](https://www.zotero.org/support/dev/web_api/v3/basics)
- [Pyzotero Documentation](https://pyzotero.readthedocs.io/)
- [CSL JSON Schema](https://citeproc-js.readthedocs.io/en/latest/csl-json/markup.html)
- [Zotero Schema](https://github.com/zotero/zotero-schema)
- [Zotero Forums](https://forums.zotero.org/)