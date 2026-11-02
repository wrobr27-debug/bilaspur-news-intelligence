"""Seed script for initial source registry population.

This script registers initial sources for the Bilaspur News Intelligence
system. Sources are marked as inactive by default until verified.

IMPORTANT:
- These are discovery targets, not verified feeds
- RSS/API URLs are stored only when verified
- Unverified sources are marked as pending verification
- Do not make all sources active by default
"""

from src.database.base import SessionLocal, engine, Base
from src.registry.source_registry import SourceRegistry
from src.database.models import Sources


def seed_initial_sources(force: bool = False):
    """Seed the source registry with initial discovery targets."""
    
    # Create tables if they don't exist
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    try:
        # Check existing sources
        existing_count = db.query(Sources).count()
        print(f"Existing sources in registry: {existing_count}")
        
        if not force and existing_count > 0:
            print("Sources already seeded. Use --force to re-seed.")
            return
        
        # Define source categories and their discovery targets
        # Government sources
        government_sources = [
            {
                "source_id": "district_administration",
                "source_name": "District Administration Bilaspur",
                "publisher_name": "Government of Chhattisgarh",
                "source_type": "government",
                "source_category": "district",
                "source_url": "https://bilaspur.gov.in/",
                "content_url": "https://bilaspur.gov.in/en/notice_category/",
                "rss_url": None,
                "api_url": None,
                "sitemap_url": None,
                "geography": "district",
                "language": "en",
                "collection_method": "html",
                "reliability_level": "official",
                "active": False,
                "collection_interval_minutes": 30,
                "terms_url": "https://bilaspur.gov.in/",
                "notes": "Bilaspur district official website - monitoring announcements, notices, tenders, recruitment",
            },
            {
                "source_id": "nagar_nigam",
                "source_name": "Nagar Nigam Bilaspur",
                "publisher_name": "Municipal Corporation",
                "source_type": "government",
                "source_category": "city",
                "source_url": "https://nigambilaspur.com/",
                "content_url": None,
                "rss_url": None,
                "api_url": None,
                "sitemap_url": None,
                "geography": "city",
                "language": "en",
                "collection_method": "html",
                "reliability_level": "official",
                "active": False,
                "collection_interval_minutes": 30,
                "terms_url": "https://nigambilaspur.com/",
                "notes": "Bilaspur Municipal Corporation - local government announcements",
            },
            {
                "source_id": "cmo_chhattisgarh",
                "source_name": "CMO Chhattisgarh",
                "publisher_name": "Chief Minister Office",
                "source_type": "government",
                "source_category": "state",
                "source_url": "https://cmo.cg.gov.in/",
                "content_url": None,
                "rss_url": None,
                "api_url": None,
                "sitemap_url": None,
                "geography": "state",
                "language": "en",
                "collection_method": "html",
                "reliability_level": "official",
                "active": False,
                "collection_interval_minutes": 30,
                "terms_url": "https://cmo.cg.gov.in/",
                "notes": "Chief Minister Office Chhattisgarh - state-level announcements. May require Playwright for JS-heavy site.",
            },
            {
                "source_id": "cg_state_gov",
                "source_name": "Chhattisgarh State Government",
                "publisher_name": "Government of Chhattisgarh",
                "source_type": "government",
                "source_category": "state",
                "source_url": "https://cgstate.gov.in/",
                "content_url": None,
                "rss_url": None,
                "api_url": None,
                "sitemap_url": None,
                "geography": "state",
                "language": "en",
                "collection_method": "html",
                "reliability_level": "official",
                "active": False,
                "collection_interval_minutes": 30,
                "terms_url": "https://cgstate.gov.in/",
                "notes": "Chhattisgarh state government portal.",
            },
            {
                "source_id": "jansampark",
                "source_name": "Jansampark Chhattisgarh",
                "publisher_name": "Chhattisgarh Government",
                "source_type": "government",
                "source_category": "state",
                "source_url": "https://jansampark.cg.gov.in/",
                "content_url": None,
                "rss_url": None,
                "api_url": None,
                "sitemap_url": None,
                "geography": "state",
                "language": "en",
                "collection_method": "html",
                "reliability_level": "official",
                "active": False,
                "collection_interval_minutes": 60,
                "terms_url": "https://jansampark.cg.gov.in/",
                "notes": "Public grievance and announcement portal.",
            },
            {
                "source_id": "icc_bilaspur_smartcity",
                "source_name": "Bilaspur Smart City",
                "publisher_name": "Bilaspur Smart City Development",
                "source_type": "government",
                "source_category": "city",
                "source_url": "https://www.icccbilaspur.in/",
                "content_url": None,
                "rss_url": None,
                "api_url": None,
                "sitemap_url": None,
                "geography": "city",
                "language": "en",
                "collection_method": "html",
                "reliability_level": "official",
                "active": False,
                "collection_interval_minutes": 60,
                "terms_url": "https://www.icccbilaspur.in/",
                "notes": "Bilaspur Smart City projects and announcements. JS-heavy, may require Playwright.",
            },
            {
                "source_id": "bilaspur_police",
                "source_name": "Bilaspur Police",
                "publisher_name": "Chhattisgarh Police",
                "source_type": "police",
                "source_category": "city",
                "source_url": "https://bilaspur.cgpolice.gov.in/",
                "content_url": None,
                "rss_url": None,
                "api_url": None,
                "sitemap_url": None,
                "geography": "city",
                "language": "en",
                "collection_method": "html",
                "reliability_level": "official",
                "active": False,
                "collection_interval_minutes": 30,
                "terms_url": "https://bilaspur.cgpolice.gov.in/",
                "notes": "Bilaspur Police official website - crime, traffic, safety announcements.",
            },
        ]
        
        # Police sources
        police_sources = [
            {
                "source_id": "cg_police",
                "source_name": "Chhattisgarh Police",
                "publisher_name": "Chhattisgarh Police Headquarters",
                "source_type": "police",
                "source_category": "state",
                "source_url": "https://cgpolice.gov.in/",
                "content_url": None,
                "rss_url": None,
                "api_url": None,
                "sitemap_url": None,
                "geography": "state",
                "language": "en",
                "collection_method": "html",
                "reliability_level": "official",
                "active": False,
                "collection_interval_minutes": 30,
                "terms_url": "https://cgpolice.gov.in/",
                "notes": "Chhattisgarh Police headquarters - state-level police announcements.",
            },
        ]
        
        # Newspaper and publisher sources
        newspaper_sources = [
            {
                "source_id": "dainik_bhaskar",
                "source_name": "Dainik Bhaskar",
                "publisher_name": "Dainik Bhaskar Group",
                "source_type": "newspaper",
                "source_category": "state",
                "source_url": "https://www.bhaskar.com/",
                "content_url": "https://www.bhaskar.com/chhattisgarh/bilaspur/",
                "rss_url": None,
                "api_url": None,
                "sitemap_url": None,
                "geography": "district",
                "language": "hi",
                "collection_method": "html",
                "reliability_level": "established_publisher",
                "active": False,
                "collection_interval_minutes": 30,
                "terms_url": "https://www.bhaskar.com/",
                "notes": "Hindi newspaper - Bilaspur Chhattisgarh section. HTML collection.",
            },
            {
                "source_id": "patrika_bilaspur",
                "source_name": "Patrika Bilaspur",
                "publisher_name": "Patrika Group",
                "source_type": "newspaper",
                "source_category": "district",
                "source_url": "https://www.patrika.com/",
                "content_url": "https://www.patrika.com/bilaspur-news/",
                "rss_url": None,
                "api_url": None,
                "sitemap_url": None,
                "geography": "district",
                "language": "hi",
                "collection_method": "html",
                "reliability_level": "established_publisher",
                "active": False,
                "collection_interval_minutes": 30,
                "terms_url": "https://www.patrika.com/",
                "notes": "Hindi newspaper - Bilaspur news section.",
            },
            {
                "source_id": "naidunia_bilaspur",
                "source_name": "Nai Dunia Bilaspur",
                "publisher_name": "Nai Dunia Group",
                "source_type": "newspaper",
                "source_category": "district",
                "source_url": "https://www.naidunia.com/",
                "content_url": "https://www.naidunia.com/chhattisgarh/bilaspur",
                "rss_url": "https://rss.jagran.com/naidunia/chhattisgarh/bilaspur.xml",
                "api_url": None,
                "sitemap_url": None,
                "geography": "district",
                "language": "hi",
                "collection_method": "rss",
                "reliability_level": "established_publisher",
                "active": False,
                "collection_interval_minutes": 30,
                "terms_url": "https://www.naidunia.com/",
                "notes": "Hindi newspaper - Verified RSS feed available.",
            },
            {
                "source_id": "haribhoomi",
                "source_name": "Hari Bhoomi",
                "publisher_name": "Hari Bhoomi Group",
                "source_type": "newspaper",
                "source_category": "state",
                "source_url": "https://www.haribhoomi.com/",
                "content_url": None,
                "rss_url": None,
                "api_url": None,
                "sitemap_url": None,
                "geography": "state",
                "language": "hi",
                "collection_method": "html",
                "reliability_level": "established_publisher",
                "active": False,
                "collection_interval_minutes": 30,
                "terms_url": "https://www.haribhoomi.com/",
                "notes": "Hindi newspaper - no RSS verified yet.",
            },
            {
                "source_id": "navabharat",
                "source_name": "Navabharat",
                "publisher_name": "Navabharat Group",
                "source_type": "newspaper",
                "source_category": "state",
                "source_url": "https://www.navabharat.com/",
                "content_url": None,
                "rss_url": None,
                "api_url": None,
                "sitemap_url": None,
                "geography": "state",
                "language": "hi",
                "collection_method": "html",
                "reliability_level": "established_publisher",
                "active": False,
                "collection_interval_minutes": 30,
                "terms_url": "https://www.navabharat.com/",
                "notes": "Hindi newspaper - no RSS verified yet.",
            },
            {
                "source_id": "lokswar",
                "source_name": "Lokswar",
                "publisher_name": "Lokswar Media",
                "source_type": "newspaper",
                "source_category": "state",
                "source_url": "https://lokswar.in/",
                "content_url": None,
                "rss_url": "https://www.lokswar.in/feed",
                "api_url": None,
                "sitemap_url": None,
                "geography": "state",
                "language": "hi",
                "collection_method": "rss",
                "reliability_level": "established_publisher",
                "active": False,
                "collection_interval_minutes": 30,
                "terms_url": "https://lokswar.in/",
                "notes": "Hindi news portal - Verified RSS feed available.",
            },
            {
                "source_id": "deshbandhu",
                "source_name": "Deshbandhu",
                "publisher_name": "Deshbandhu Group",
                "source_type": "newspaper",
                "source_category": "state",
                "source_url": "https://www.deshbandhu.co.in/",
                "content_url": None,
                "rss_url": None,
                "api_url": None,
                "sitemap_url": None,
                "geography": "state",
                "language": "en",
                "collection_method": "html",
                "reliability_level": "established_publisher",
                "active": False,
                "collection_interval_minutes": 30,
                "terms_url": "https://www.deshbandhu.co.in/",
                "notes": "English newspaper - Bilaspur coverage.",
            },
        ]
        
        # Television and video sources
        tv_sources = [
            {
                "source_id": "ibc24",
                "source_name": "IBC24",
                "publisher_name": "IBC24 Group",
                "source_type": "television",
                "source_category": "state",
                "source_url": "https://www.ibc24.in/",
                "content_url": None,
                "rss_url": None,
                "api_url": None,
                "sitemap_url": None,
                "geography": "state",
                "language": "hi",
                "collection_method": "html",
                "reliability_level": "established_publisher",
                "active": False,
                "collection_interval_minutes": 60,
                "terms_url": "https://www.ibc24.in/",
                "notes": "Hindi news channel - may have YouTube channel for video content.",
            },
            {
                "source_id": "news18_cg",
                "source_name": "News18 Chhattisgarh",
                "publisher_name": "Network18",
                "source_type": "television",
                "source_category": "state",
                "source_url": "https://hindi.news18.com/",
                "content_url": None,
                "rss_url": None,
                "api_url": None,
                "sitemap_url": None,
                "geography": "state",
                "language": "hi",
                "collection_method": "html",
                "reliability_level": "established_publisher",
                "active": False,
                "collection_interval_minutes": 60,
                "terms_url": "https://hindi.news18.com/",
                "notes": "Hindi news channel.",
            },
            {
                "source_id": "etv_bharat",
                "source_name": "ETV Bharat",
                "publisher_name": "BVG Pvt Ltd",
                "source_type": "television",
                "source_category": "state",
                "source_url": "https://www.etvbharat.com/",
                "content_url": None,
                "rss_url": None,
                "api_url": None,
                "sitemap_url": None,
                "geography": "state",
                "language": "hi",
                "collection_method": "html",
                "reliability_level": "established_publisher",
                "active": False,
                "collection_interval_minutes": 60,
                "terms_url": "https://www.etvbharat.com/",
                "notes": "Hindi news portal.",
            },
        ]
        
        # Education sources
        education_sources = [
            {
                "source_id": "ggu",
                "source_name": "Guru Ghasidas Vishwavidyalaya",
                "publisher_name": "GGV University",
                "source_type": "education",
                "source_category": "city",
                "source_url": "https://www.ggu.ac.in/",
                "content_url": None,
                "rss_url": None,
                "api_url": None,
                "sitemap_url": None,
                "geography": "city",
                "language": "en",
                "collection_method": "html",
                "reliability_level": "official",
                "active": False,
                "collection_interval_minutes": 60,
                "terms_url": "https://www.ggu.ac.in/",
                "notes": "Central University Bilaspur - academic announcements, exams, results.",
            },
            {
                "source_id": "vbvu",
                "source_name": "Atal Bihari Vajpayee Vishwavidyalaya",
                "publisher_name": "ABVV University",
                "source_type": "education",
                "source_category": "city",
                "source_url": "https://www.bilaspuruniversity.ac.in/",
                "content_url": None,
                "rss_url": None,
                "api_url": None,
                "sitemap_url": None,
                "geography": "city",
                "language": "en",
                "collection_method": "html",
                "reliability_level": "official",
                "active": False,
                "collection_interval_minutes": 60,
                "terms_url": "https://www.bilaspuruniversity.ac.in/",
                "notes": "State university Bilaspur - academic announcements.",
            },
            {
                "source_id": "vyapam",
                "source_name": "Vyapam CG",
                "publisher_name": "Professional Examination Board",
                "source_type": "education",
                "source_category": "state",
                "source_url": "https://vyapam.cgstate.gov.in/",
                "content_url": None,
                "rss_url": None,
                "api_url": None,
                "sitemap_url": None,
                "geography": "state",
                "language": "en",
                "collection_method": "html",
                "reliability_level": "official",
                "active": False,
                "collection_interval_minutes": 60,
                "terms_url": "https://vyapam.cgstate.gov.in/",
                "notes": "Chhattisgarh Professional Examination Board - recruitment, exams.",
            },
            {
                "source_id": "psc_cg",
                "source_name": "PSC Chhattisgarh",
                "publisher_name": "Public Service Commission",
                "source_type": "education",
                "source_category": "state",
                "source_url": "https://psc.cg.gov.in/",
                "content_url": None,
                "rss_url": None,
                "api_url": None,
                "sitemap_url": None,
                "geography": "state",
                "language": "en",
                "collection_method": "html",
                "reliability_level": "official",
                "active": False,
                "collection_interval_minutes": 60,
                "terms_url": "https://psc.cg.gov.in/",
                "notes": "Chhattisgarh PSC - government job recruitment.",
            },
        ]
        
        # Railway and transport sources
        transport_sources = [
            {
                "source_id": "sec_railway",
                "source_name": "SECR Bilaspur Railway Division",
                "publisher_name": "South East Central Railway",
                "source_type": "transport",
                "source_category": "district",
                "source_url": "https://secr.indianrailways.gov.in/",
                "content_url": None,
                "rss_url": None,
                "api_url": None,
                "sitemap_url": None,
                "geography": "district",
                "language": "en",
                "collection_method": "html",
                "reliability_level": "official",
                "active": False,
                "collection_interval_minutes": 60,
                "terms_url": "https://secr.indianrailways.gov.in/",
                "notes": "Bilaspur Railway Division - train schedules, announcements, project updates.",
            },
            {
                "source_id": "irctc",
                "source_name": "IRCTC",
                "publisher_name": "Indian Railway Catering",
                "source_type": "transport",
                "source_category": "regional",
                "source_url": "https://www.irctc.co.in/",
                "content_url": None,
                "rss_url": None,
                "api_url": None,
                "sitemap_url": None,
                "geography": "regional",
                "language": "en",
                "collection_method": "html",
                "reliability_level": "official",
                "active": False,
                "collection_interval_minutes": 120,
                "terms_url": "https://www.irctc.co.in/",
                "notes": "IRCTC for ticket booking and railway updates.",
            },
            {
                "source_id": "parivahan",
                "source_name": "Parivahan CG",
                "publisher_name": "Ministry of Road Transport",
                "source_type": "transport",
                "source_category": "state",
                "source_url": "https://parivahan.gov.in/",
                "content_url": None,
                "rss_url": None,
                "api_url": None,
                "sitemap_url": None,
                "geography": "state",
                "language": "en",
                "collection_method": "html",
                "reliability_level": "official",
                "active": False,
                "collection_interval_minutes": 120,
                "terms_url": "https://parivahan.gov.in/",
                "notes": "Road transport and highways updates.",
            },
        ]
        
        # Health sources
        health_sources = [
            {
                "source_id": "cg_health",
                "source_name": "Chhattisgarh Health Department",
                "publisher_name": "Government of Chhattisgarh",
                "source_type": "health",
                "source_category": "state",
                "source_url": "https://cghealth.nic.in/",
                "content_url": None,
                "rss_url": None,
                "api_url": None,
                "sitemap_url": None,
                "geography": "state",
                "language": "en",
                "collection_method": "html",
                "reliability_level": "official",
                "active": False,
                "collection_interval_minutes": 60,
                "terms_url": "https://cghealth.nic.in/",
                "notes": "Chhattisgarh Health Department - health advisories, schemes.",
            },
            {
                "source_id": "nhm_cg",
                "source_name": "National Health Mission CG",
                "publisher_name": "NHM Chhattisgarh",
                "source_type": "health",
                "source_category": "state",
                "source_url": "https://nhm.gov.in/",
                "content_url": None,
                "rss_url": None,
                "api_url": None,
                "sitemap_url": None,
                "geography": "state",
                "language": "en",
                "collection_method": "html",
                "reliability_level": "official",
                "active": False,
                "collection_interval_minutes": 60,
                "terms_url": "https://nhm.gov.in/",
                "notes": "National Health Mission - state updates.",
            },
        ]
        
        # Business and industry sources
        business_sources = [
            {
                "source_id": "secl",
                "source_name": "South Eastern Coalfields Limited",
                "publisher_name": "SECL",
                "source_type": "business",
                "source_category": "district",
                "source_url": "https://www.secl-cil.in/",
                "content_url": None,
                "rss_url": None,
                "api_url": None,
                "sitemap_url": None,
                "geography": "district",
                "language": "en",
                "collection_method": "html",
                "reliability_level": "official",
                "active": False,
                "collection_interval_minutes": 60,
                "terms_url": "https://www.secl-cil.in/",
                "notes": "SECL Bilaspur - coal mining operations, announcements.",
            },
            {
                "source_id": "ntpc_cg",
                "source_name": "NTPC Chhattisgarh",
                "publisher_name": "NTPC",
                "source_type": "business",
                "source_category": "state",
                "source_url": "https://ntpc.co.in/",
                "content_url": None,
                "rss_url": None,
                "api_url": None,
                "sitemap_url": None,
                "geography": "state",
                "language": "en",
                "collection_method": "html",
                "reliability_level": "official",
                "active": False,
                "collection_interval_minutes": 60,
                "terms_url": "https://ntpc.co.in/",
                "notes": "NTPC Chhattisgarh power plant announcements.",
            },
        ]
        
        # Agriculture and environment sources
        agriculture_sources = [
            {
                "source_id": "agriportal_cg",
                "source_name": "Agriportal Chhattisgarh",
                "publisher_name": "Government of Chhattisgarh",
                "source_type": "agriculture",
                "source_category": "state",
                "source_url": "https://agriportal.cg.nic.in/",
                "content_url": None,
                "rss_url": None,
                "api_url": None,
                "sitemap_url": None,
                "geography": "state",
                "language": "en",
                "collection_method": "html",
                "reliability_level": "official",
                "active": False,
                "collection_interval_minutes": 120,
                "terms_url": "https://agriportal.cg.nic.in/",
                "notes": "Agriculture portal - schemes, crop information.",
            },
            {
                "source_id": "forest_cg",
                "source_name": "Forest Department CG",
                "publisher_name": "Forest Department",
                "source_type": "environment",
                "source_category": "state",
                "source_url": "https://forest.cg.gov.in/",
                "content_url": None,
                "rss_url": None,
                "api_url": None,
                "sitemap_url": None,
                "geography": "state",
                "language": "en",
                "collection_method": "html",
                "reliability_level": "official",
                "active": False,
                "collection_interval_minutes": 120,
                "terms_url": "https://forest.cg.gov.in/",
                "notes": "Forest department - environmental issues, alerts.",
            },
            {
                "source_id": "cpcb",
                "source_name": "CPCB India",
                "publisher_name": "Central Pollution Control Board",
                "source_type": "environment",
                "source_category": "regional",
                "source_url": "https://cpcb.nic.in/",
                "content_url": None,
                "rss_url": None,
                "api_url": None,
                "sitemap_url": None,
                "geography": "regional",
                "language": "en",
                "collection_method": "html",
                "reliability_level": "official",
                "active": False,
                "collection_interval_minutes": 120,
                "terms_url": "https://cpcb.nic.in/",
                "notes": "Central pollution control - regional air/water quality.",
            },
        ]
        
        # Collect all source definitions
        all_sources = (
            government_sources
            + police_sources
            + newspaper_sources
            + tv_sources
            + education_sources
            + transport_sources
            + health_sources
            + business_sources
            + agriculture_sources
        )
        
        # Add each source to the registry
        added = 0
        for source_data in all_sources:
            # Check if source already exists
            existing = SourceRegistry.get_source(db, source_data["source_id"])
            if existing and not force:
                print(f"  Skipping {source_data['source_id']}: already exists")
                continue
            
            if existing and force:
                # Update existing source
                for key, value in source_data.items():
                    setattr(existing, key, value)
                db.commit()
                print(f"  Updated: {source_data['source_id']}")
                added += 1
                continue
            
            # Create new source
            source = SourceRegistry.add_source(db, **source_data)
            print(f"  Added: {source_data['source_id']} - {source.source_name}")
            added += 1
        
        db.commit()
        print(f"\n✓ Successfully seeded {added} sources")
        print(f"  Total in registry: {db.query(Sources).count()}")
        print("\nImportant: Most sources are marked inactive (active=False)")
        print("  until they are verified and their collection methods confirmed.")
        print("  Use 'python -m main sources check' to verify sources.")
        
    except Exception as e:
        db.rollback()
        print(f"✗ Error seeding sources: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    import sys
    force_flag = "--force" in sys.argv
    seed_initial_sources(force=force_flag)