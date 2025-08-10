#!/usr/bin/env python3
"""
Papers3 Publications Extractor

This script extracts all publications from a Papers3 database
and generates a JSON representation with metadata.

Usage:
    python papers3_publications.py [database_path] [--full] [--human-readable] [--include-all]
    
Default database path: Database.papersdb
--full: Export full related entity details instead of just UUIDs
--human-readable: Use first 75 characters of names instead of UUIDs
--include-all: Include all publications (default: only publications with content)
"""

import sqlite3
import json
import sys
import os
from typing import Dict, List, Any, Optional
from datetime import datetime


class Papers3PublicationsExtractor:
    def __init__(self, database_path: str = "Database.papersdb", full_export: bool = False, human_readable: bool = False, include_all: bool = False):
        self.database_path = database_path
        self.full_export = full_export
        self.human_readable = human_readable
        self.include_all = include_all
        self.publications = {}
        self.publication_authors = {}
        self.publication_pdfs = {}
        self.publication_collections = {}
        self.publication_keywords = {}
        self.publication_bundles = {}
        
        # Publication type mapping from papers3_publication_types.json
        self.publication_types = {
            # Main types
            999: "Paper",
            400: "Article", 
            0: "Book",
            300: "Media",
            500: "Patent",
            700: "Report",
            -100: "Periodical",
            -200: "Conference",
            -300: "Website",
            # Article subtypes
            401: "Journal Article",
            402: "Magazine Article", 
            403: "Newspaper Article",
            420: "Review Article",
            410: "Conference Paper",
            415: "Conference Poster",
            # Book subtypes
            1: "Book Chapter",
            20: "Edited Book",
            40: "Textbook",
            30: "Reference Book",
            10: "Thesis/Dissertation",
            -1000: "Manual",
            -1010: "Handbook",
            99: "Other Book",
            # Media subtypes
            318: "Video",
            301: "Film",
            302: "Television",
            303: "Radio",
            311: "Audio",
            317: "Podcast",
            312: "Music",
            310: "Sound Recording",
            316: "Interview",
            315: "Lecture",
            319: "Presentation",
            350: "Dataset",
            313: "Image",
            314: "Photograph",
            320: "Map",
            326: "Chart",
            322: "Graph",
            327: "Diagram",
            323: "Figure",
            324: "Illustration",
            328: "Drawing",
            325: "Painting",
            331: "Sculpture",
            329: "Artwork",
            330: "Exhibition",
            321: "Poster",
            341: "Software",
            344: "Application",
            345: "Database",
            340: "Code",
            # Patent subtypes
            525: "Patent Application",
            524: "Patent Document",
            520: "Utility Patent",
            527: "Design Patent",
            522: "Plant Patent",
            511: "Patent Specification",
            523: "Patent Claim",
            521: "Patent Abstract",
            528: "Patent Drawing",
            510: "Patent Search Report",
            526: "Patent Office Action",
            # Report subtypes
            704: "Technical Report",
            711: "Research Report",
            712: "Working Paper",
            713: "Discussion Paper",
            702: "White Paper",
            701: "Policy Paper",
            703: "Case Study",
            716: "Evaluation Report",
            722: "Annual Report",
            718: "Progress Report",
            710: "Feasibility Study",
            719: "Impact Assessment",
            723: "Literature Review",
            717: "Survey Report",
            720: "Market Report",
            721: "Financial Report",
            715: "Audit Report",
            714: "Compliance Report",
            799: "Other Report",
            750: "Government Document",
            # Periodical subtypes
            -110: "Magazine",
            -101: "Newsletter",
            -102: "Bulletin",
            # Conference subtypes
            -201: "Symposium",
            -202: "Workshop",
            -205: "Seminar",
            -203: "Congress",
            -204: "Meeting"
        }
        
    def connect_database(self) -> sqlite3.Connection:
        """Connect to the Papers3 SQLite database."""
        if not os.path.exists(self.database_path):
            raise FileNotFoundError(f"Database file not found: {self.database_path}")
        
        return sqlite3.connect(self.database_path)
    
    def _convert_publication_type(self, type_value: Optional[int]) -> Optional[str]:
        """Convert publication type integer to readable name."""
        if type_value is None:
            return None
        type_name = self.publication_types.get(type_value, f"unknown_{type_value}")
        return type_name.lower() if type_name else None
    
    def get_publications(self, conn: sqlite3.Connection) -> Dict[str, Dict[str, Any]]:
        """Extract all publications with their metadata."""
        cursor = conn.cursor()
        
        query = """
        SELECT 
            uuid,
            title,
            subtitle,
            author_string,
            publication_date,
            doi,
            publisher,
            volume,
            number,
            startpage,
            endpage,
            type,
            subtype,
            rating,
            read_status,
            flagged,
            notes,
            keyword_string,
            times_cited,
            times_read,
            language,
            status,
            summary,
            institution,
            bundle,
            created_at,
            updated_at
        FROM Publication
        ORDER BY title
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        publications = {}
        for row in rows:
            publication = {
                "uuid": row[0],
                "title": row[1],
                "subtitle": row[2],
                "author_string": row[3],
                "publication_date": self._convert_publication_date(row[4]),
                "doi": row[5],
                "publisher": row[6],
                "volume": row[7],
                "number": row[8],
                "startpage": row[9],
                "endpage": row[10],
                "pages": f"{row[9]}-{row[10]}" if row[9] and row[10] else None,
                "type": self._convert_publication_type(row[11]),
                "subtype": self._convert_publication_type(row[12]),
                "rating": row[13],
                "read_status": row[14],
                "flagged": bool(row[15]) if row[15] is not None else None,
                "notes": row[16],
                "keyword_string": row[17],
                "times_cited": row[18],
                "times_read": row[19],
                "language": row[20],
                "status": row[21],
                "summary": row[22],
                "institution": row[23],
                "bundle": row[24],
                "created_at": self._format_timestamp(row[25]),
                "updated_at": self._format_timestamp(row[26]),
                "authors": [],
                "pdfs": [],
                "collections": [],
                "keywords": []
            }
            publications[row[0]] = publication
            
        return publications
    
    def get_publication_authors(self, conn: sqlite3.Connection) -> Dict[str, List[Dict[str, Any]]]:
        """Extract all authors for each publication."""
        cursor = conn.cursor()
        
        if self.full_export:
            # Full export with all author details
            query = """
            SELECT 
                oa.object_id,
                oa.author_id,
                oa.priority,
                oa.type,
                oa.created_at,
                oa.updated_at,
                a.fullname,
                a.prename,
                a.surname,
                a.initial,
                a.standard_name,
                a.nickname,
                a.email,
                a.affiliation,
                a.location,
                a.post_title,
                a.pre_title,
                a.notes,
                a.institutional,
                a.is_me,
                a.flagged,
                a.publication_count,
                a.type as author_type
            FROM OrderedAuthor oa
            JOIN Author a ON oa.author_id = a.uuid
            ORDER BY oa.object_id, oa.priority
            """
            
            cursor.execute(query)
            rows = cursor.fetchall()
            
            publication_authors = {}
            for row in rows:
                item = {
                    "author_uuid": row[1],
                    "priority": row[2],
                    "type": self._convert_author_type(row[3]),
                    "created_at": self._format_timestamp(row[4]),
                    "updated_at": self._format_timestamp(row[5]),
                    "fullname": row[6],
                    "prename": row[7],
                    "surname": row[8],
                    "initial": row[9],
                    "standard_name": row[10],
                    "nickname": row[11],
                    "email": row[12],
                    "affiliation": row[13],
                    "location": row[14],
                    "post_title": row[15],
                    "pre_title": row[16],
                    "notes": row[17],
                    "institutional": bool(row[18]) if row[18] is not None else None,
                    "is_me": bool(row[19]) if row[19] is not None else None,
                    "flagged": bool(row[20]) if row[20] is not None else None,
                    "publication_count": row[21],
                    "author_type": self._convert_author_type(row[22])
                }
                
                pub_uuid = row[0]
                if pub_uuid not in publication_authors:
                    publication_authors[pub_uuid] = []
                publication_authors[pub_uuid].append(item)
        else:
            # Lightweight export with UUIDs and optionally names
            if self.human_readable:
                query = """
                SELECT 
                    oa.object_id,
                    oa.author_id,
                    oa.priority,
                    a.fullname
                FROM OrderedAuthor oa
                JOIN Author a ON oa.author_id = a.uuid
                ORDER BY oa.object_id, oa.priority
                """
                
                cursor.execute(query)
                rows = cursor.fetchall()
                
                publication_authors = {}
                for row in rows:
                    name = row[3] if row[3] else "Unknown Author"
                    name_preview = name[:75] + "..." if len(name) > 75 else name
                    
                    item = {
                        "author_uuid": row[1],
                        "name_preview": name_preview,
                        "priority": row[2]
                    }
                    
                    pub_uuid = row[0]
                    if pub_uuid not in publication_authors:
                        publication_authors[pub_uuid] = []
                    publication_authors[pub_uuid].append(item)
            else:
                query = """
                SELECT 
                    oa.object_id,
                    oa.author_id,
                    oa.priority
                FROM OrderedAuthor oa
                ORDER BY oa.object_id, oa.priority
                """
                
                cursor.execute(query)
                rows = cursor.fetchall()
                
                publication_authors = {}
                for row in rows:
                    item = {
                        "author_uuid": row[1],
                        "priority": row[2]
                    }
                    
                    pub_uuid = row[0]
                    if pub_uuid not in publication_authors:
                        publication_authors[pub_uuid] = []
                    publication_authors[pub_uuid].append(item)
            
        return publication_authors
    
    def get_publication_pdfs(self, conn: sqlite3.Connection) -> Dict[str, List[Dict[str, Any]]]:
        """Extract all PDFs for each publication."""
        cursor = conn.cursor()
        
        if self.full_export:
            # Full export with all PDF details
            query = """
            SELECT 
                pdf.object_id,
                pdf.uuid,
                pdf.caption,
                pdf.fingerprint,
                pdf.md5,
                pdf.mime_type,
                pdf.pages,
                pdf.is_primary,
                pdf.is_alias,
                pdf.missing,
                pdf.needs_ocr,
                pdf.rotation,
                pdf.type,
                pdf.searchresult,
                pdf.created_at,
                pdf.updated_at,
                pdf.path,
                pdf.original_path
            FROM PDF pdf
            WHERE pdf.object_id IS NOT NULL
            ORDER BY pdf.object_id, pdf.caption
            """
            
            cursor.execute(query)
            rows = cursor.fetchall()
            
            publication_pdfs = {}
            for row in rows:
                item = {
                    "pdf_uuid": row[1],
                    "caption": row[2],
                    "fingerprint": row[3],
                    "md5": row[4],
                    "mime_type": row[5],
                    "pages": row[6],
                    "is_primary": bool(row[7]) if row[7] is not None else None,
                    "is_alias": bool(row[8]) if row[8] is not None else None,
                    "missing": bool(row[9]) if row[9] is not None else None,
                    "needs_ocr": bool(row[10]) if row[10] is not None else None,
                    "rotation": row[11],
                    "type": row[12],
                    "searchresult": row[13],
                    "created_at": self._format_timestamp(row[14]),
                    "updated_at": self._format_timestamp(row[15]),
                    "path": row[16],
                    "original_path": row[17]
                }
                
                pub_uuid = row[0]
                if pub_uuid not in publication_pdfs:
                    publication_pdfs[pub_uuid] = []
                publication_pdfs[pub_uuid].append(item)
        else:
            # Lightweight export with UUIDs and optionally captions
            if self.human_readable:
                query = """
                SELECT 
                    pdf.object_id,
                    pdf.uuid,
                    pdf.caption
                FROM PDF pdf
                WHERE pdf.object_id IS NOT NULL
                ORDER BY pdf.object_id, pdf.caption
                """
                
                cursor.execute(query)
                rows = cursor.fetchall()
                
                publication_pdfs = {}
                for row in rows:
                    caption = row[2] if row[2] else "Untitled PDF"
                    caption_preview = caption[:75] + "..." if len(caption) > 75 else caption
                    
                    item = {
                        "pdf_uuid": row[1],
                        "caption_preview": caption_preview
                    }
                    
                    pub_uuid = row[0]
                    if pub_uuid not in publication_pdfs:
                        publication_pdfs[pub_uuid] = []
                    publication_pdfs[pub_uuid].append(item)
            else:
                query = """
                SELECT 
                    pdf.object_id,
                    pdf.uuid
                FROM PDF pdf
                WHERE pdf.object_id IS NOT NULL
                ORDER BY pdf.object_id
                """
                
                cursor.execute(query)
                rows = cursor.fetchall()
                
                publication_pdfs = {}
                for row in rows:
                    item = {
                        "pdf_uuid": row[1]
                    }
                    
                    pub_uuid = row[0]
                    if pub_uuid not in publication_pdfs:
                        publication_pdfs[pub_uuid] = []
                    publication_pdfs[pub_uuid].append(item)
            
        return publication_pdfs
    
    def get_publication_collections(self, conn: sqlite3.Connection) -> Dict[str, List[Dict[str, Any]]]:
        """Extract all collections for each publication."""
        cursor = conn.cursor()
        
        if self.full_export:
            # Full export with all collection details
            query = """
            SELECT 
                ci.object_id,
                ci.collection,
                ci.priority,
                ci.privacy_level,
                ci.type,
                ci.created_at,
                ci.updated_at,
                c.name,
                c.parent,
                c.collection_description,
                c.created_at as coll_created_at,
                c.updated_at as coll_updated_at
            FROM CollectionItem ci
            JOIN Collection c ON ci.collection = c.uuid
            ORDER BY ci.object_id, ci.priority
            """
            
            cursor.execute(query)
            rows = cursor.fetchall()
            
            publication_collections = {}
            for row in rows:
                item = {
                    "collection_uuid": row[1],
                    "priority": row[2],
                    "privacy_level": row[3],
                    "type": row[4],
                    "created_at": self._format_timestamp(row[5]),
                    "updated_at": self._format_timestamp(row[6]),
                    "name": row[7],
                    "parent": row[8],
                    "collection_description": row[9],
                    "collection_created_at": self._format_timestamp(row[10]),
                    "collection_updated_at": self._format_timestamp(row[11])
                }
                
                pub_uuid = row[0]
                if pub_uuid not in publication_collections:
                    publication_collections[pub_uuid] = []
                publication_collections[pub_uuid].append(item)
        else:
            # Lightweight export with UUIDs and optionally names
            if self.human_readable:
                query = """
                SELECT 
                    ci.object_id,
                    ci.collection,
                    ci.priority,
                    c.name
                FROM CollectionItem ci
                JOIN Collection c ON ci.collection = c.uuid
                ORDER BY ci.object_id, ci.priority
                """
                
                cursor.execute(query)
                rows = cursor.fetchall()
                
                publication_collections = {}
                for row in rows:
                    name = row[3] if row[3] else "Unnamed Collection"
                    name_preview = name[:75] + "..." if len(name) > 75 else name
                    
                    item = {
                        "collection_uuid": row[1],
                        "name_preview": name_preview,
                        "priority": row[2]
                    }
                    
                    pub_uuid = row[0]
                    if pub_uuid not in publication_collections:
                        publication_collections[pub_uuid] = []
                    publication_collections[pub_uuid].append(item)
            else:
                query = """
                SELECT 
                    ci.object_id,
                    ci.collection,
                    ci.priority
                FROM CollectionItem ci
                ORDER BY ci.object_id, ci.priority
                """
                
                cursor.execute(query)
                rows = cursor.fetchall()
                
                publication_collections = {}
                for row in rows:
                    item = {
                        "collection_uuid": row[1],
                        "priority": row[2]
                    }
                    
                    pub_uuid = row[0]
                    if pub_uuid not in publication_collections:
                        publication_collections[pub_uuid] = []
                    publication_collections[pub_uuid].append(item)
            
        return publication_collections
    
    def get_publication_keywords(self, conn: sqlite3.Connection) -> Dict[str, List[Dict[str, Any]]]:
        """Extract all keywords for each publication."""
        cursor = conn.cursor()
        
        if self.full_export:
            # Full export with all keyword details
            query = """
            SELECT 
                ki.object_id,
                ki.keyword_id,
                ki.priority,
                ki.created_at,
                ki.updated_at,
                k.name,
                k.parent,
                k.canonical_name,
                k.created_at as kw_created_at,
                k.updated_at as kw_updated_at
            FROM KeywordItem ki
            JOIN Keyword k ON ki.keyword_id = k.uuid
            ORDER BY ki.object_id, ki.priority
            """
            
            cursor.execute(query)
            rows = cursor.fetchall()
            
            publication_keywords = {}
            for row in rows:
                item = {
                    "keyword_uuid": row[1],
                    "priority": row[2],
                    "created_at": self._format_timestamp(row[3]),
                    "updated_at": self._format_timestamp(row[4]),
                    "name": row[5],
                    "parent": row[6],
                    "canonical_name": row[7],
                    "keyword_created_at": self._format_timestamp(row[8]),
                    "keyword_updated_at": self._format_timestamp(row[9])
                }
                
                pub_uuid = row[0]
                if pub_uuid not in publication_keywords:
                    publication_keywords[pub_uuid] = []
                publication_keywords[pub_uuid].append(item)
        else:
            # Lightweight export with UUIDs and optionally names
            if self.human_readable:
                query = """
                SELECT 
                    ki.object_id,
                    ki.keyword_id,
                    ki.priority,
                    k.name
                FROM KeywordItem ki
                JOIN Keyword k ON ki.keyword_id = k.uuid
                ORDER BY ki.object_id, ki.priority
                """
                
                cursor.execute(query)
                rows = cursor.fetchall()
                
                publication_keywords = {}
                for row in rows:
                    name = row[3] if row[3] else "Unnamed Keyword"
                    name_preview = name[:75] + "..." if len(name) > 75 else name
                    
                    item = {
                        "keyword_uuid": row[1],
                        "name_preview": name_preview,
                        "priority": row[2]
                    }
                    
                    pub_uuid = row[0]
                    if pub_uuid not in publication_keywords:
                        publication_keywords[pub_uuid] = []
                    publication_keywords[pub_uuid].append(item)
            else:
                query = """
                SELECT 
                    ki.object_id,
                    ki.keyword_id,
                    ki.priority
                FROM KeywordItem ki
                ORDER BY ki.object_id, ki.priority
                """
                
                cursor.execute(query)
                rows = cursor.fetchall()
                
                publication_keywords = {}
                for row in rows:
                    item = {
                        "keyword_uuid": row[1],
                        "priority": row[2]
                    }
                    
                    pub_uuid = row[0]
                    if pub_uuid not in publication_keywords:
                        publication_keywords[pub_uuid] = []
                    publication_keywords[pub_uuid].append(item)
            
        return publication_keywords
    
    def get_publication_bundles(self, conn: sqlite3.Connection) -> Dict[str, Dict[str, Any]]:
        """Extract bundle information for publications that have bundles."""
        cursor = conn.cursor()
        
        if self.full_export:
            # Full export with all bundle details
            query = """
            SELECT 
                p.uuid as publication_uuid,
                p.bundle,
                b.title as bundle_title,
                b.subtitle as bundle_subtitle,
                b.type as bundle_type,
                b.subtype as bundle_subtype,
                b.publisher as bundle_publisher,
                b.abbreviation as bundle_abbreviation,
                b.volume as bundle_volume,
                b.number as bundle_number,
                b.publication_date as bundle_publication_date,
                b.notes as bundle_notes,
                b.created_at as bundle_created_at,
                b.updated_at as bundle_updated_at
            FROM Publication p
            JOIN Publication b ON p.bundle = b.uuid
            WHERE p.bundle IS NOT NULL
            ORDER BY p.uuid
            """
            
            cursor.execute(query)
            rows = cursor.fetchall()
            
            publication_bundles = {}
            for row in rows:
                item = {
                    "bundle_uuid": row[1],
                    "title": row[2],
                    "subtitle": row[3],
                    "type": self._convert_publication_type(row[4]),
                    "subtype": self._convert_publication_type(row[5]),
                    "publisher": row[6],
                    "abbreviation": row[7],
                    "volume": row[8],
                    "number": row[9],
                    "publication_date": self._convert_publication_date(row[10]),
                    "notes": row[11],
                    "created_at": self._format_timestamp(row[12]),
                    "updated_at": self._format_timestamp(row[13])
                }
                
                pub_uuid = row[0]
                publication_bundles[pub_uuid] = item
        else:
            # Lightweight export with basic bundle info
            if self.human_readable:
                query = """
                SELECT 
                    p.uuid as publication_uuid,
                    p.bundle,
                    b.title as bundle_title,
                    b.type as bundle_type
                FROM Publication p
                JOIN Publication b ON p.bundle = b.uuid
                WHERE p.bundle IS NOT NULL
                ORDER BY p.uuid
                """
                
                cursor.execute(query)
                rows = cursor.fetchall()
                
                publication_bundles = {}
                for row in rows:
                    title = row[2] if row[2] else "Untitled Bundle"
                    title_preview = title[:75] + "..." if len(title) > 75 else title
                    
                    item = {
                        "bundle_uuid": row[1],
                        "title_preview": title_preview,
                        "type": self._convert_publication_type(row[3])
                    }
                    
                    pub_uuid = row[0]
                    publication_bundles[pub_uuid] = item
            else:
                query = """
                SELECT 
                    p.uuid as publication_uuid,
                    p.bundle
                FROM Publication p
                WHERE p.bundle IS NOT NULL
                ORDER BY p.uuid
                """
                
                cursor.execute(query)
                rows = cursor.fetchall()
                
                publication_bundles = {}
                for row in rows:
                    item = {
                        "bundle_uuid": row[1]
                    }
                    
                    pub_uuid = row[0]
                    publication_bundles[pub_uuid] = item
            
        return publication_bundles
    
    def _convert_author_type(self, type_value: Optional[int]) -> Optional[str]:
        """Convert author type integer to lowercase name."""
        if type_value is None:
            return None
            
        type_mapping = {
            0: "author",
            1: "editor", 
            2: "photographer",
            3: "translator"
        }
        
        return type_mapping.get(type_value, f"unknown_{type_value}")
    
    def build_publications_with_relations(self, publications: Dict[str, Dict[str, Any]], 
                                        publication_authors: Dict[str, List[Dict[str, Any]]],
                                        publication_pdfs: Dict[str, List[Dict[str, Any]]],
                                        publication_collections: Dict[str, List[Dict[str, Any]]],
                                        publication_keywords: Dict[str, List[Dict[str, Any]]],
                                        publication_bundles: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Build the publications list with their related entities."""
        # Add authors to publications
        for pub_uuid, authors in publication_authors.items():
            if pub_uuid in publications:
                if self.full_export:
                    publications[pub_uuid]["authors"] = authors
                else:
                    if self.human_readable:
                        publications[pub_uuid]["authors"] = [author["name_preview"] for author in authors]
                    else:
                        publications[pub_uuid]["authors"] = [author["author_uuid"] for author in authors]
                publications[pub_uuid]["author_count"] = len(authors)
        
        # Add PDFs to publications
        for pub_uuid, pdfs in publication_pdfs.items():
            if pub_uuid in publications:
                if self.full_export:
                    publications[pub_uuid]["pdfs"] = pdfs
                else:
                    if self.human_readable:
                        publications[pub_uuid]["pdfs"] = [pdf["caption_preview"] for pdf in pdfs]
                    else:
                        publications[pub_uuid]["pdfs"] = [pdf["pdf_uuid"] for pdf in pdfs]
                publications[pub_uuid]["pdf_count"] = len(pdfs)
        
        # Add collections to publications
        for pub_uuid, collections in publication_collections.items():
            if pub_uuid in publications:
                if self.full_export:
                    publications[pub_uuid]["collections"] = collections
                else:
                    if self.human_readable:
                        publications[pub_uuid]["collections"] = [coll["name_preview"] for coll in collections]
                    else:
                        publications[pub_uuid]["collections"] = [coll["collection_uuid"] for coll in collections]
                publications[pub_uuid]["collection_count"] = len(collections)
        
        # Add keywords to publications
        for pub_uuid, keywords in publication_keywords.items():
            if pub_uuid in publications:
                if self.full_export:
                    publications[pub_uuid]["keywords"] = keywords
                else:
                    if self.human_readable:
                        publications[pub_uuid]["keywords"] = [kw["name_preview"] for kw in keywords]
                    else:
                        publications[pub_uuid]["keywords"] = [kw["keyword_uuid"] for kw in keywords]
                publications[pub_uuid]["keyword_count"] = len(keywords)
        
        # Add bundles to publications
        for pub_uuid, bundle in publication_bundles.items():
            if pub_uuid in publications:
                if self.full_export:
                    publications[pub_uuid]["bundle_details"] = bundle
                else:
                    if self.human_readable:
                        publications[pub_uuid]["bundle"] = bundle["title_preview"]
                    else:
                        publications[pub_uuid]["bundle"] = bundle["bundle_uuid"]
        
        # Filter publications based on include_all parameter
        if not self.include_all:
            # Only include publications with content (authors, PDFs, or collections)
            publications_list = [pub for pub in publications.values() 
                               if pub.get("authors") or pub.get("pdfs") or pub.get("collections")]
        else:
            # Include all publications
            publications_list = list(publications.values())
        
        # Sort by title
        publications_list.sort(key=lambda x: (x.get("title") or "", x.get("uuid") or ""))
        
        return publications_list
    
    def get_publication_statistics(self, publications: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Generate statistics about the publications."""
        total_publications = len(publications)
        
        # Count by type
        type_counts = {}
        for pub in publications.values():
            pub_type = pub.get("type", "Unknown")
            type_counts[pub_type] = type_counts.get(pub_type, 0) + 1
        
        # Count by year
        year_counts = {}
        for pub in publications.values():
            pub_date = pub.get("publication_date")
            if pub_date:
                try:
                    year = int(pub_date[:4])  # Extract year from date string
                    year_counts[year] = year_counts.get(year, 0) + 1
                except (ValueError, TypeError):
                    pass
        
        # Count publications with various attributes
        with_authors = sum(1 for pub in publications.values() if pub.get("authors"))
        with_pdfs = sum(1 for pub in publications.values() if pub.get("pdfs"))
        with_collections = sum(1 for pub in publications.values() if pub.get("collections"))
        with_keywords = sum(1 for pub in publications.values() if pub.get("keywords"))
        with_bundles = sum(1 for pub in publications.values() if pub.get("bundle") or pub.get("bundle_details"))
        with_doi = sum(1 for pub in publications.values() if pub.get("doi"))
        flagged = sum(1 for pub in publications.values() if pub.get("flagged"))
        
        # Calculate averages
        total_authors = sum(len(pub.get("authors", [])) for pub in publications.values())
        total_pdfs = sum(len(pub.get("pdfs", [])) for pub in publications.values())
        total_collections = sum(len(pub.get("collections", [])) for pub in publications.values())
        total_keywords = sum(len(pub.get("keywords", [])) for pub in publications.values())
        
        return {
            "total_publications": total_publications,
            "publications_with_authors": with_authors,
            "publications_with_pdfs": with_pdfs,
            "publications_with_collections": with_collections,
            "publications_with_keywords": with_keywords,
            "publications_with_bundles": with_bundles,
            "publications_with_doi": with_doi,
            "flagged_publications": flagged,
            "total_authors": total_authors,
            "total_pdfs": total_pdfs,
            "total_collections": total_collections,
            "total_keywords": total_keywords,
            "average_authors_per_publication": total_authors / total_publications if total_publications > 0 else 0,
            "average_pdfs_per_publication": total_pdfs / total_publications if total_publications > 0 else 0,
            "average_collections_per_publication": total_collections / total_publications if total_publications > 0 else 0,
            "average_keywords_per_publication": total_keywords / total_publications if total_publications > 0 else 0,
            "type_distribution": type_counts,
            "year_distribution": year_counts
        }
    
    def _format_timestamp(self, timestamp: Optional[float]) -> Optional[str]:
        """Convert Unix timestamp to readable date string."""
        if timestamp is None:
            return None
        try:
            return datetime.fromtimestamp(timestamp).isoformat()
        except (ValueError, OSError):
            return str(timestamp)
    
    def _convert_publication_date(self, date_string: Optional[str]) -> Optional[str]:
        """Convert Papers3 publication date format to ISO format."""
        if not date_string or len(date_string) < 14:
            return None
        
        try:
            # Format: 99YYYYMMDDHHMMSS00000000222000
            # Extract the date part: 99YYYYMMDDHHMMSS
            if date_string.startswith('99') and len(date_string) >= 16:
                date_part = date_string[2:16]  # Remove '99' prefix and get YYYYMMDDHHMMSS
                
                # Parse the components
                year = int(date_part[0:4])
                month = int(date_part[4:6])
                day = int(date_part[6:8])
                hour = int(date_part[8:10])
                minute = int(date_part[10:12])
                second = int(date_part[12:14])
                
                # Handle invalid dates (month 00, day 00)
                if month == 0:
                    month = 1
                if day == 0:
                    day = 1
                
                # Validate the date
                if year < 1900 or year > 2100 or month < 1 or month > 12 or day < 1 or day > 31:
                    # If date is invalid, return year only
                    return f"{year}-01-01T00:00:00"
                
                # Create datetime object
                dt = datetime(year, month, day, hour, minute, second)
                return dt.isoformat()
            else:
                # Try to parse as regular date string
                return date_string
        except (ValueError, TypeError):
            # If parsing fails, return the original string
            return date_string
    
    def extract_publications(self) -> Dict[str, Any]:
        """Main method to extract publications and their related entities."""
        print(f"Connecting to database: {self.database_path}")
        
        with self.connect_database() as conn:
            print("Extracting publications...")
            publications = self.get_publications(conn)
            
            print("Extracting publication authors...")
            publication_authors = self.get_publication_authors(conn)
            
            print("Extracting publication PDFs...")
            publication_pdfs = self.get_publication_pdfs(conn)
            
            print("Extracting publication collections...")
            publication_collections = self.get_publication_collections(conn)
            
            print("Extracting publication keywords...")
            publication_keywords = self.get_publication_keywords(conn)
            
            print("Extracting publication bundles...")
            publication_bundles = self.get_publication_bundles(conn)
            
            print("Building publications with relations...")
            publications_list = self.build_publications_with_relations(
                publications, publication_authors, publication_pdfs, 
                publication_collections, publication_keywords, publication_bundles
            )
            
            print("Generating statistics...")
            statistics = self.get_publication_statistics(publications)
            
            result = {
                "metadata": {
                    "database_path": self.database_path,
                    "extraction_date": datetime.now().isoformat(),
                    "statistics": statistics
                },
                "publications": publications_list
            }
            
            return result
    
    def save_json(self, data: Dict[str, Any], output_path: str = "papers3_publications.json"):
        """Save the publications data to a JSON file."""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Publications data saved to: {output_path}")


def main():
    """Main function to run the publications extractor."""
    # Parse command line arguments
    args = sys.argv[1:]
    database_path = "Database.papersdb"
    full_export = False
    human_readable = False
    include_all = False
    
    for arg in args:
        if arg == "--full":
            full_export = True
        elif arg == "--human-readable":
            human_readable = True
        elif arg == "--include-all":
            include_all = True
        elif not arg.startswith("--"):
            database_path = arg
    
    try:
        # Create extractor and extract data
        extractor = Papers3PublicationsExtractor(database_path, full_export, human_readable, include_all)
        publications_data = extractor.extract_publications()
        
        # Save to JSON file
        output_file = "papers3_publications.json"
        if full_export:
            output_file = "papers3_publications_full.json"
        elif human_readable:
            output_file = "papers3_publications_human.json"
        if include_all:
            output_file = output_file.replace(".json", "_all.json")
        extractor.save_json(publications_data, output_file)
        
        # Print summary
        stats = publications_data["metadata"]["statistics"]
        if full_export:
            export_type = "Full"
        elif human_readable:
            export_type = "Human-Readable"
        else:
            export_type = "Lightweight"
        scope = "All Publications" if include_all else "Publications with Content Only"
        print(f"\nExtraction Summary ({export_type} Export, {scope}):")
        print(f"  Total publications: {stats['total_publications']}")
        print(f"  Publications with authors: {stats['publications_with_authors']}")
        print(f"  Publications with PDFs: {stats['publications_with_pdfs']}")
        print(f"  Publications with collections: {stats['publications_with_collections']}")
        print(f"  Publications with keywords: {stats['publications_with_keywords']}")
        print(f"  Publications with bundles: {stats['publications_with_bundles']}")
        print(f"  Publications with DOI: {stats['publications_with_doi']}")
        print(f"  Flagged publications: {stats['flagged_publications']}")
        print(f"  Total authors: {stats['total_authors']}")
        print(f"  Total PDFs: {stats['total_pdfs']}")
        print(f"  Total collections: {stats['total_collections']}")
        print(f"  Total keywords: {stats['total_keywords']}")
        print(f"  Average authors per publication: {stats['average_authors_per_publication']:.1f}")
        print(f"  Average PDFs per publication: {stats['average_pdfs_per_publication']:.1f}")
        print(f"  Average collections per publication: {stats['average_collections_per_publication']:.1f}")
        print(f"  Average keywords per publication: {stats['average_keywords_per_publication']:.1f}")
        print(f"  Output file: {output_file}")
        
        # Print top publication types
        if stats['type_distribution']:
            print(f"\nTop publication types:")
            sorted_types = sorted(stats['type_distribution'].items(), key=lambda x: x[1], reverse=True)
            for pub_type, count in sorted_types[:5]:
                print(f"  {pub_type}: {count}")
        
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 