# Operation Manual English — <DATASET_OPERATION_GUIDE> (en)

> Source: Standard Operating Manual for Charging Piles.docx (English original, 35 chapters, 190 paragraphs)  
> Usage: SPEC-D3 Path C operation guidance, node 5030/5031/5032  
> Retrieval: multi_retrieval, metadata filter language=en

## 35 Chapters × 3 Endpoints

### PC Management Backend (16 chapters)
- Role Management / Shop Level / Individual operator
- Operator review for entry / Add sites under the operator / Site audit
- Billing Template (Charging Station) / Add product model / equipment
- Placement equipment / Charging coupons / Equipment Failure List
- User Management / Financial Management / Order Management
- Operations Management / Data View

### User End C-side (9 chapters)
- Sign up / top-up / place an order
- Four wheel charging order / Placeholder fee order
- venue / license plate / Change password / Fault Repair

### Butler End B-side (10 chapters)
- Sign up / Real name authentication / Create venue / my venue
- Create template / Venue association template / Placement equipment
- data sector / order / Venue details / Profit withdrawal

## Field Schema

| Column | Type | Description |
|--------|------|-------------|
| chapter | string | 35 top-level chapter |
| endpoint | enum | user / butler / pc |
| step | int | step number |
| step_text_en | text | English step text |
| deep_link | string | jump path |
| notes | text | notes |

## Placeholder Samples

### Role Management (pc) steps 1-3
1. Enter the system → Role Management
2. Click the add button to add a role
3. Complete the form: Select the end type, role name, role type, and role code, and click save

### Fault Repair (user)
1. Open App, click "My" → "Fault Repair"
- deep_link: /charge/pages/malfunction/malfunction
- 5032 MUST preserve this link

### Placeholder fee order (user)
1. View fee details on placeholder fee order page
- deep_link: /charge/pages/placeUseFeeList/placeUseFeeList
- 5032 MUST preserve

### Profit withdrawal (butler)
1. Butler Home → My → Profit Withdrawal
2. Fill amount → Bank card → Submit for review
- notes: T+1 settlement

## Key Constraints (5032)

⚠️ deep_link strings MUST be preserved verbatim:
- /charge/pages/malfunction/malfunction
- /charge/pages/placeUseFeeList/placeUseFeeList
- /admin/system/role
- ... 30+ links

## TODO
- [ ] Extract complete steps for all 35 chapters (200+ steps)
- [ ] Complete deep_link list
- [ ] Cross-reference FAQ 21 nodes
