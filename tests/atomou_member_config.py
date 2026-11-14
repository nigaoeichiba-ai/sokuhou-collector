"""atomou: the membership and plan settings that sites/atomou/config.json had until 2026-11-14 (the owner put the subscription on hold and took the membership off).
The code for them is still in the repository and still tested: the tests that drive it build the site with these settings added back (`{**CFG, **MEMBER_CONFIG}`).
To bring the membership back to the site, put these keys back into sites/atomou/config.json (atomou/docs/SUBSCRIPTION_RESTORE.md says what else to restore)."""
MEMBER_CONFIG = {
    "member_mail_from": "noreply@atomou.com",
    "member_tiers": [
        {"id": "tester", "label": "先着モニター", "size": 30, "months": 18, "tester": True},
        {"id": "first", "label": "先着", "size": 270, "months": 12},
    ],
    "member_ref_months": 6,
    "member_ref_cap": 12,
    "member_ref_give_months": 1,
    "plans": {"on": True, "plus_open": False, "free_cards": 5, "free_shared": 2, "shares_per_slot": 3, "extra_max": 20, "free_remind": [7, 1]},
}
