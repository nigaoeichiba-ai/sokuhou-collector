"""List editorial price review dates and their private source references."""
import argparse
from datetime import date, timedelta

from case_articles import CASES, AVERAGE
from case_finances import SOURCES

REVIEWS = {
    "case-family-trip": (14, ("rail", "stay", "stay_tax", "kyoto_bus", "reserved")),
    "case-weeknight-dinner": (14, ("deli", "cook", "kit", "deli_delivery", "deli_shipping", "deli_frozen",
                                  "dinner_rice", "dinner_side", "dinner_soup")),
    "case-temporary-appliances": (30, ("rental", "rental_setup", "rental_area", "purchase", "recycle",
                                      "recycle_dropoff", "purchase_delivered", "purchase_pickup", "purchase_recycle")),
    "article": (30, ("stamp", "brokerage")),
    "travel-cost-average": (180, ("tourism",)),
}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    parser.add_argument("--due", action="store_true", help="期限が来た記事だけを表示")
    args = parser.parse_args()
    for case in (*CASES, AVERAGE):
        days, refs = REVIEWS[case["slug"]]
        checked = date.fromisoformat(case["checked"])
        expires = checked + timedelta(days=days)
        if args.due and expires > args.as_of:
            continue
        print(f"{case['slug']}.html  確認 {checked}  次回 {expires}")
        for ref in refs:
            print(f"  {SOURCES[ref]}")
