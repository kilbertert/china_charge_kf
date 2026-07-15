"""Build MANIFEST.md from _manifest_stub.csv by adding retrieval-style descriptions.

Each description is written as a customer question so the LLM KB can match it
when a user asks how to do something on the charging pile platform.
"""
from __future__ import annotations

import csv
from pathlib import Path

KB_DIR = Path(r"d:/AI/company-projects/ai-customer/china_charge_kf/kb-assets")
STUB_CSV = KB_DIR / "_intermediates" / "_manifest_stub.csv"
MANIFEST = KB_DIR / "MANIFEST.md"

DESCRIPTIONS: dict[str, str] = {
    # ---------------- PC backend ----------------
    "pc-backend-role-management-1.png":
        "How do I open the Role Management page in the PC admin backend to create a new role and assign end-type permissions?",
    "pc-backend-role-management-operator-1.png":
        "How do I assign or check Operator permissions when adding a role in the PC backend role management list?",
    "pc-backend-role-management-permissions-1.png":
        "How do I edit the permissions of an existing role and tick the permission boxes before clicking update?",
    "pc-backend-role-management-permissions-2.png":
        "How do I click the Add button on the role permissions page to start creating a brand-new role entry?",
    "pc-backend-shop-level-1.png":
        "How do I configure shop-level commission rules in the PC backend and click Add to create a transaction-amount tier?",
    "pc-backend-shop-level-by-transaction-amount-1.png":
        "How do I set a shop-level commission based on transaction amount brackets with different service-fee rates?",
    "pc-backend-shop-level-by-charging-degree-1.png":
        "How do I create a shop-level commission template that calculates the service fee by charging degree instead of amount?",
    "pc-backend-individual-operator-1.png":
        "How do I find the Individual Operator list page in the PC backend and click Add to onboard a new operator?",
    "pc-backend-individual-operator-add-individual-operator-1.png":
        "How do I fill in the form to add a new individual operator under a parent operator in the PC backend?",
    "pc-backend-individual-operator-add-individual-operator-2.png":
        "What fields are required when registering an individual operator such as phone, role, and region in the backend?",
    "pc-backend-individual-operator-add-individual-operator-3.png":
        "How do I confirm and save a newly added individual operator so it appears in the operator list immediately?",
    "pc-backend-individual-operator-edit-operator-info-1.png":
        "How do I edit an existing operator's personal information and contact details from the PC backend operator list?",
    "pc-backend-individual-operator-edit-operator-info-2.png":
        "How do I choose the communication channel used to configure a project when updating an operator profile?",
    "pc-backend-operator-review-1.png":
        "How do I review and approve an operator entry application from the Operator Review queue in the PC backend?",
    "pc-backend-add-sites-1.png":
        "How do I add a new charging site under an operator account using the PC backend venue management menu?",
    "pc-backend-add-sites-add-venue-1.png":
        "How do I register a new four-wheel new-energy venue by filling out the Add Venue form in the PC backend?",
    "pc-backend-add-sites-add-venue-2.png":
        "How do I confirm and submit a new venue so it becomes available for site audit by the PC admin team?",
    "pc-backend-site-audit-1.png":
        "How do I open the Site Audit page and select a submitted venue to review its application details?",
    "pc-backend-site-audit-audit-1.png":
        "How do I approve or reject a pending venue application from the Audit list in the PC management backend?",
    "pc-backend-billing-template-domestic-four-wheel-1.png":
        "How do I create a time-of-use peak and valley billing template for domestic four-wheel EV chargers in the backend?",
    "pc-backend-billing-template-domestic-four-wheel-2.png":
        "How do I set peak, flat, and valley electricity prices when configuring a four-wheel charging billing template?",
    "pc-backend-billing-template-domestic-four-wheel-3.png":
        "How do I save the domestic four-wheel billing template so it can be linked to a charging site later?",
    "pc-backend-billing-template-seat-occupancy-fee-1.png":
        "How do I add a new occupancy-fee billing template for charging spots from the backend fee-standard menu?",
    "pc-backend-billing-template-seat-occupancy-fee-2.png":
        "How do I configure the per-minute or per-hour occupancy fee rules inside a spot occupancy billing template?",
    "pc-backend-billing-template-point-award-1.png":
        "How do I add a points-award template that rewards users with bonus points after each charging session?",
    "pc-backend-billing-template-point-award-2.png":
        "How do I set the point calculation formula and rate inside a points-award template in the PC backend?",
    "pc-backend-billing-template-point-award-3.png":
        "How do I save a points-award billing template and link it to a venue so users earn points when charging?",
    "pc-backend-billing-template-venue-configuration-1.png":
        "How do I configure which billing templates are applied to a specific venue from the venue configuration page?",
    "pc-backend-billing-template-venue-configuration-2.png":
        "How do I bind a billing template, occupancy fee, and points template to a venue in the PC backend?",
    "pc-backend-billing-template-venue-configuration-3.png":
        "How do I verify a venue's billing-template bindings after configuration is complete in the PC backend?",
    "pc-backend-billing-template-venue-configuration-4.png":
        "How do I save and apply the configured venue billing templates so they take effect for end users?",
    "pc-backend-add-product-model-1.png":
        "How do I add a new charging-pile equipment type by filling in its equipment number, name, and protocol in the backend?",
    "pc-backend-add-product-model-cloud-fast-charging-1.png":
        "How do I open the Management of Charging Pile Models list to register a cloud fast-charging protocol device?",
    "pc-backend-equipment-1.png":
        "How do I add a new device type with charging-pile protocol, power rating, and gun type in the equipment page?",
    "pc-backend-equipment-add-device-1.png":
        "How do I add a single charging device by entering its serial number and binding it to a venue in the backend?",
    "pc-backend-equipment-remote-device-startup-1.png":
        "How do I remotely start a charging device from the equipment list when the user cannot trigger it locally?",
    "pc-backend-placement-equipment-placement-1.png":
        "How do I place a charging pile on a venue by selecting the site and confirming the equipment placement form?",
    "pc-backend-charging-coupons-1.png":
        "How do I create a new charging coupon by filling in the name, validity period, and discount rule in the backend?",
    "pc-backend-charging-coupons-platform-coupon-1.png":
        "How do I open the Platform Coupon list under Marketing Management and click Create coupon in the PC backend?",
    "pc-backend-charging-coupons-venue-coupon-1.png":
        "How do I create a venue-scoped coupon that can only be claimed at a specific charging site?",
    "pc-backend-charging-coupons-distribute-coupons-1.png":
        "How do I issue a coupon to specific users by selecting their phone numbers in the backend distribution dialog?",
    "pc-backend-equipment-failure-list-1.png":
        "How do I view the Equipment Failure List to find reported charging pile faults and their review status?",
    "pc-backend-user-management-1.png":
        "How do I open the Member List to search, filter, and manage end-user accounts in the PC backend?",
    "pc-backend-financial-management-verify-recharge-1.png":
        "How do I open the Recharge dialog and verify a user's top-up request by selecting the member and entering the amount?",
    "pc-backend-financial-management-verify-recharge-2.png":
        "How do I send a verification code to my admin phone to confirm and save a backend recharge operation?",
    "pc-backend-financial-management-withdrawal-review-1.png":
        "How do I open the Withdrawal Application page to review a user's pending withdrawal request in the backend?",
    "pc-backend-financial-management-balance-details-1.png":
        "How do I view a user's balance change history under Asset Management to trace each recharge and deduction?",
    "pc-backend-financial-management-settlement-statement-1.png":
        "How do I generate and export the Charging Settlement Statement showing electricity, service, and gun fees per order?",
    "pc-backend-financial-management-settlement-statement-2.png":
        "How do I read a per-order settlement row showing electricity bill, service fee, gun charge, and parking fee?",
    "pc-backend-financial-management-settlement-statement-3.png":
        "How do I review and issue a pending reconciliation bill to an operator or site after a settlement period closes?",
    "pc-backend-order-management-charging-order-1.png":
        "How do I view the EV Charging Order list and check user, gun, and energy details for every charging session?",
    "pc-backend-order-management-occupancy-fee-order-1.png":
        "How do I open the Occupancy Fee Order list to see charging-time, space amount, and payment status for each spot?",
    "pc-backend-order-management-abnormal-charging-monitoring-1.png":
        "How do I find abnormal charging orders in the monitoring tab to investigate stalls or stuck-gun errors?",
    "pc-backend-order-management-order-evaluation-1.png":
        "How do I review user-submitted ratings and comments for a charging order in the Order Evaluation page?",
    "pc-backend-operations-management-article-guide-1.png":
        "How do I add a new Article Category so I can publish operation guides under it in the PC backend?",
    "pc-backend-operations-management-article-guide-2.png":
        "How do I navigate to Article Content and click Add to start creating a new operation guide article?",
    "pc-backend-operations-management-article-guide-3.png":
        "How do I fill in the article title, intro, picture, and tags when creating a new operation guide in the backend?",
    "pc-backend-operations-management-article-guide-4.png":
        "How do I save and publish an operation guide article so it becomes visible to the C-end user app?",
    "pc-backend-operations-management-protocol-privacy-1.png":
        "How do I add a new User Privacy Agreement or Privacy Policy protocol from the Protocol List in the backend?",
    "pc-backend-operations-management-protocol-privacy-2.png":
        "How do I enable a privacy policy so it is automatically shown on the user registration page?",
    "pc-backend-data-view-1.png":
        "How do I open the Charging Station Monitoring view to see charging pile status, faults, and utilization per site?",
    "pc-backend-data-view-2.png":
        "How do I read the Trends in Site Utilization chart to monitor charging-pile usage over a selected week or month?",
    "pc-backend-data-view-3.png":
        "How do I open the Site Data Dashboard to check charging cost, order count, users, and energy for a venue?",
    # ---------------- User side ----------------
    "user-side-sign-up-login-and-registration-1.png":
        "How do I sign up for the charging app with my phone number, verification code, and password on the user side?",
    "user-side-top-up-recharge-1.png":
        "How do I recharge my account balance by tapping Balance then choosing an amount and paying in the user app?",
    "user-side-place-order-scan-to-order-1.png":
        "How do I open the Orders tab from My profile to find and place a new charging order in the user app?",
    "user-side-place-order-scan-to-order-2.png":
        "How do I scan the QR code on a charger to start a charging session and tap Get start to begin charging?",
    "user-side-four-wheel-charging-order-1.png":
        "How do I view my four-wheel charging orders list and check each session's QR, equipment code, and status?",
    "user-side-placeholder-fee-order-1.png":
        "How do I open the Occupancy Orders list to see my parking or spot placeholder fee history in the user app?",
    "user-side-my-vehicle-1.png":
        "How do I tap Addition of vehicle on My vehicle to add a new EV car with license plate and VIN?",
    "user-side-license-plate-1.png":
        "How do I add a new EV license plate by entering the plate number, VIN, and selecting brand and model?",
    "user-side-license-plate-license-plate-1.png":
        "How do I bind my license plate to a charging session so the system auto-recognizes my car at the charger?",
    "user-side-change-password-1.png":
        "How do I reset or change my password using phone verification code from the Forgot password screen in the app?",
    "user-side-fault-repair-1.png":
        "How do I report a charging fault by entering the gun code, describing the problem, and uploading a photo?",
    # ---------------- Butler end ----------------
    "butler-end-sign-up-login-operator-1.png":
        "How do I log in to the butler-end operator app with my account number and password as a charging station partner?",
    "butler-end-sign-up-register-operator-1.png":
        "How do I register a new operator account and start a Partner application on the butler-end mobile app?",
    "butler-end-real-name-authentication-1.png":
        "How do I complete real-name authentication and link my ID card and bank card to enable cash withdrawal?",
    "butler-end-create-venue-1.png":
        "How do I tap New venue on the home screen and submit a new charging venue application from the butler app?",
    "butler-end-create-template-creating-billing-template-1.png":
        "How do I create a new four-wheel billing template by selecting a venue and setting minimum-startup rules?",
    "butler-end-venue-association-template-associated-billing-1.png":
        "How do I bind a charging billing template to my venue from the Billing Settings tab in the butler app?",
    "butler-end-venue-association-template-associated-occupancy-1.png":
        "How do I associate an Occupancy Fee Template with my venue so spot fees are charged after charging ends?",
    "butler-end-venue-association-template-associate-point-award-1.png":
        "How do I associate a default points-award template with my venue so users automatically earn reward points?",
    "butler-end-placement-equipment-placement-1.png":
        "How do I deploy a charging device to my venue by selecting site, billing template, and point-award rules?",
    "butler-end-data-sector-four-wheel-data-1.png":
        "How do I read the Business Data dashboard on the home page showing today's electricity, income, and gun status?",
    "butler-end-order-four-round-order-1.png":
        "How do I open Four wheel charging order to review recent orders, settlement amount, and charging details?",
    "butler-end-venue-details-four-wheel-venue-1.png":
        "How do I tap my venue name to open Venue details and check online devices, turnover, and device settings?",
    "butler-end-profit-withdrawal-1.png":
        "How do I apply for cash withdrawal from My commission by entering the amount and tapping Apply in the butler app?",
}


def main() -> None:
    rows = list(csv.DictReader(STUB_CSV.open(encoding="utf-8")))
    missing: list[str] = []
    for r in rows:
        fn = r["new_filename"]
        if fn not in DESCRIPTIONS:
            missing.append(fn)
        else:
            r["description"] = DESCRIPTIONS[fn]

    if missing:
        raise SystemExit(f"Missing descriptions for: {missing}")

    lines: list[str] = ["# Image Manifest — Charging Pile KB", ""]
    lines.append("| # | Filename | Context heading | Description | Suggested OSS key | Notes |")
    lines.append("|---|----------|-----------------|-------------|--------------------|-------|")
    for r in rows:
        notes = r.get("notes", "")
        lines.append(
            f"| {r['order']} | `{r['new_filename']}` | "
            f"{r['context_heading']} | {r['description']} | `{r['oss_key']}` | {notes} |"
        )

    MANIFEST.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote MANIFEST.md with {len(rows)} rows -> {MANIFEST}")


if __name__ == "__main__":
    main()
