# Papers3 Database Extraction Tools

This repository contains tools for extracting and analyzing data from Papers3 bibliographic database files. Papers3 is a reference management application for macOS that stores bibliographic data in SQLite databases.

## Overview

The Papers3 database contains a comprehensive collection of academic publications, authors, PDFs, keywords, and collections. This toolset provides scripts to extract this data into structured JSON formats for analysis, migration, or integration with other systems.

## Database Location

To obtain the database file to run the scripts on:
1. Navigate to the folder `CompressedCheckpoints` inside the `Library.papers3` folder on Dropbox.  
2. Download the latest checkpoint file and append the `.zip` extension. Unzip the file
3. Optionally rename the file to `Database.papersdb` or explicitely add the database path when running the scripts.

## Database Structure

### Core Entities

The Papers3 database is organized around these main entities (stats from a large example library):

#### **Publications** (3,930 records)
- **Types**: Articles (3,128), Periodicals/Journals (802)
- **Fields**: Title, authors, publication date, DOI, publisher, volume, pages, etc.
- **Relationships**: Connected to authors, PDFs, collections, keywords, and bundles

#### **Authors** (11,499 records)
- **Fields**: Full name, prename, surname, email, affiliation, institutional status
- **Relationships**: Many-to-many with publications via OrderedAuthor table
- **Ordering**: Author priority maintained for proper citation order

#### **PDFs** (2,938 records)
- **Storage**: Hybrid approach - metadata in database, files in filesystem
- **Fields**: File paths, page count, fingerprint, MD5 hash, view settings
- **Relationships**: One-to-one with publications

#### **Keywords** (4,040 records)
- **Fields**: Name, canonical name, hierarchical structure
- **Relationships**: Many-to-many with publications via KeywordItem table

#### **Collections** (25 records)
- **Purpose**: Organizational folders/categories
- **Fields**: Name, description, parent-child relationships
- **Relationships**: Many-to-many with publications via CollectionItem table

### Key Relationships

```
Publication (uuid) ←→ PDF (object_id)
Publication (uuid) ←→ OrderedAuthor (object_id)
Publication (uuid) ←→ CollectionItem (object_id)
Publication (uuid) ←→ KeywordItem (object_id)
Publication (uuid) ←→ Bundle (self-referencing)
```

### Bundle System

Publications can be grouped into "bundles" (journals, conferences, etc.):
- **Articles** (type 400) → linked to **Periodicals** (type -100)
- **Self-referencing**: Bundle field points to another Publication record
- **Example**: Journal article → "Nature" journal bundle

## Extraction Scripts

### 1. `papers3_publications.py`

Extracts all publications with their complete metadata and relationships.

**Usage:**
```bash
# Basic extraction
python papers3_publications.py

# Human-readable output (titles instead of UUIDs)
python papers3_publications.py --human-readable

# Full export with complete entity details
python papers3_publications.py --full

# Include all publications (even those without relationships)
python papers3_publications.py --include-all
```

**Output Files:**
- `papers3_publications.json` - Lightweight export
- `papers3_publications_human.json` - Human-readable export
- `papers3_publications_full.json` - Full export with complete details

**Features:**
- Extracts publications, authors, PDFs, collections, keywords, and bundles
- Converts publication dates from Papers3 format to ISO 8601
- Provides comprehensive statistics
- Handles invalid dates gracefully
- Lowercase type/subtype conversion

### 2. `papers3_authors.py`

Extracts all authors with their publication relationships.

**Usage:**
```bash
python papers3_authors.py [--full] [--human-readable] [--include-all]
```

**Features:**
- Author metadata extraction
- Publication relationships
- Author type classification (author, editor, translator, etc.)
- Statistics and analysis

### 3. `papers3_pdfs.py`

Extracts PDF metadata and file information.

**Usage:**
```bash
python papers3_pdfs.py [--full] [--human-readable] [--include-all]
```

**Features:**
- PDF file metadata
- File path reconstruction
- Integrity checking (MD5, fingerprint)
- Missing file detection

### 4. `papers3_collections.py`

Extracts collection structure and contents.

**Usage:**
```bash
python papers3_collections.py [--full] [--human-readable] [--include-all]
```

**Features:**
- Collection hierarchy
- Publication assignments
- Collection metadata

## Data Formats

### Publication Date Format

**Papers3 Format:** `99YYYYMMDDHHMMSS00000000222000`
- `99` - Prefix
- `YYYY` - Year (4 digits)
- `MM` - Month (2 digits)
- `DD` - Day (2 digits)
- `HH` - Hour (2 digits)
- `MM` - Minute (2 digits)
- `SS` - Second (2 digits)
- `00000000222000` - Padding

**Converted Format:** `YYYY-MM-DDTHH:MM:SS` (ISO 8601)

### Publication Types

**Main Types:**
- `400` → `article` - Journal articles, research papers
- `-100` → `periodical` - Journals, magazines
- `0` → `book` - Books and book chapters
- `300` → `media` - Videos, images, datasets
- `500` → `patent` - Patents and applications
- `700` → `report` - Technical reports

**Subtypes:** 89 different subtypes available (see `papers3_publication_types.json`)

## Library Statistics

Based on the analyzed database used to build the scripts:

- **Total Publications**: 3,930
- **Articles**: 3,128 (79.6%)
- **Journals**: 802 (20.4%)
- **Authors**: 11,499
- **PDFs**: 2,938
- **Keywords**: 4,040
- **Collections**: 25
- **Date Range**: 1990-2014

## File Organization

### Database Files
- `Database.papersdb` - Main SQLite database
- `Database.papersdb-*.db` - Backup/archive versions
- `PredicateEditor.plist` - Publication type definitions
- `TableColumns.plist` - Column configurations

### Output Files
- `papers3_*.json` - Extracted data in JSON format
- `papers3_*_human.json` - Human-readable versions
- `papers3_*_full.json` - Complete data with all relationships

## PDF File Reconstruction

Papers3 uses a hybrid storage approach:

1. **Metadata**: Stored in database (paths, fingerprints, etc.)
2. **Files**: Stored in filesystem with structured organization
3. **Paths**: Both relative and absolute paths tracked
4. **Integrity**: MD5 hashes and fingerprints for verification

**File Structure:**
```
Articles/
├── 2014/
│   └── Al/
│       └── 2014 Al.pdf
├── 2008/
│   └── Invitrogen/
│       └── 2008 Invitrogen.pdf
```

## Usage Examples

### Basic Extraction
```bash
# Extract all publications
python papers3_publications.py

# Extract with human-readable names
python papers3_publications.py --human-readable
```

### Analysis
```bash
# Get full details for analysis
python papers3_publications.py --full

# Include all entities (even those without relationships)
python papers3_publications.py --include-all
```

### Data Processing
The JSON output can be easily processed with tools like:
- **Python**: `json`, `pandas`
- **JavaScript**: `JSON.parse()`
- **R**: `jsonlite`
- **Command line**: `jq`

## Technical Details

### Database Schema
- **SQLite 3.x** database
- **UUID-based** primary keys
- **Foreign key** relationships with referential integrity
- **Triggers** for change logging
- **Comprehensive indexing**

### Change Tracking
- 91,070 changes logged in `changeLog` table
- Timestamps, table names, and field modifications tracked
- Enables synchronization and conflict resolution

### Data Integrity
- **Cascade deletes** for related records
- **Restrict deletes** for referenced entities
- **MD5 hashes** for file integrity
- **Fingerprints** for unique identification

## Research Focus

The analyzed database appears to focus on:
- **Biological sciences** (developmental biology, genetics)
- **Medical research** (cancer, neurology)
- **Academic publications** (journal articles, research papers)
- **Time period**: 1990-2014

## Requirements

- **Python 3.6+**
- **SQLite3** (usually included with Python)
- **Standard library modules**: `sqlite3`, `json`, `datetime`, `typing`

## License

This toolset is provided for educational and research purposes. Papers3 is a commercial product by Mekentosj / ReadCube.

## Contributing

Feel free to submit issues, feature requests, or pull requests to improve these extraction tools.

---

*Generated from Papers3 database analysis - Last updated: 2025-08-06* 