import sys
from pathlib import Path

# Add backend to path so imports work
sys.path.insert(0, str(Path(__file__).parent))

from utils.database import init_db, seed_from_excel, DB_PATH

def main():
    # ── Locate Excel files ─────────────────────────────────────────────────
    if len(sys.argv) == 4:
        ds1 = Path(sys.argv[1])
        ds3 = Path(sys.argv[2])
        ds4 = Path(sys.argv[3])
    else:
        # Default: look in backend/../data/ or backend/../
        base = Path(__file__).parent.parent
        candidates = [
            base / "data",
            base,
            Path(__file__).parent,
        ]
        ds1 = ds3 = ds4 = None
        for folder in candidates:
            if (folder / "DS1_new_policy_registration_FIXED.xlsx").exists():
                ds1 = folder / "DS1_new_policy_registration_FIXED.xlsx"
                ds3 = folder / "DS3_policy_renewal_FIXED.xlsx"
                ds4 = folder / "DS4_claims_FIXED.xlsx"
                break

    if not ds1 or not ds1.exists():
        print("ERROR: Could not find Excel files.")
        print("Usage: python seed_db.py <DS1.xlsx> <DS3.xlsx> <DS4.xlsx>")
        print("Or place the Excel files in the project root folder.")
        sys.exit(1)

    print(f"Using:")
    print(f"  DS1: {ds1}")
    print(f"  DS3: {ds3}")
    print(f"  DS4: {ds4}")
    print()

    # ── Init schema ────────────────────────────────────────────────────────
    print("Creating database schema...")
    init_db()

    # ── Seed data ──────────────────────────────────────────────────────────
    print("Seeding data from Excel files...")
    seed_from_excel(ds1, ds3, ds4)

    print(f"\nDone! Database created at: {DB_PATH}")
    print("\nNext steps:")
    print("  1. Start backend:  uvicorn backend.app.main:app --reload --port 8000")
    print("  2. Test lookup:    GET http://localhost:8000/api/v1/renewal/policy/NP00000001")

if __name__ == "__main__":
    main()
