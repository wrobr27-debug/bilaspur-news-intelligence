from src.main import run_collect
import sys

# Run collection with social media enabled
try:
    run_collect(social=True)
    print("\nCollection completed successfully!")
except SystemExit as e:
    print(f"\nCollection exited with code: {e.code}")
except Exception as e:
    print(f"\nCollection error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()