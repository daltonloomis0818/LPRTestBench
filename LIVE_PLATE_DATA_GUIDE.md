# LIVE_PLATE_DATA_GUIDE.md — Trade Show Demo Data Refresh

**Audience:** Claude Code (future sessions).
**Purpose:** Maintain a dedicated demo property in PMS (PPOA) + PatriotLPR so the Patriot LPR mobile app shows a full edge-case suite during trade shows. Walk-up signups automatically land on this property.

---

## 1. How Dalton Invokes This

> "Refresh demo data, show today 10am-4pm Central"

That one sentence is the whole input. You (Claude):

1. Read this file end-to-end.
2. Read `DevVault/AZURE_SQL_QUERY_GUIDE.md` for the query tool + security rules.
3. Determine if **One-Time Setup (Part A)** has been completed. Run the preflight check in §4 — if it returns a valid property row, skip Part A and go straight to **Per-Show Refresh (Part B)**.
4. Compute `SHOW_MID_UTC` from the show window.
5. Present the SQL plan, wait for `execute`.
6. Run writes in order: PMS first, then PatriotLPR mirror, then plate_list.txt.

If no times given — ask once. Do not assume.

---

## 2. Hard Constraints (NON-NEGOTIABLE)

1. **READ-ONLY by default.** Follow `DevVault/AZURE_SQL_QUERY_GUIDE.md`. Every write MUST be previewed (exact SQL) and approved before execution.
2. **Target property ONLY:** PMS "Patriot Ridge Apartments" (code `PLPR-DEMO`) / PatriotLPR Property `999000`.
3. **NEVER touch any other PropertyId.** Production data is off-limits.
4. **NEVER `DELETE` permits.** Void stale demo permits via `UPDATE PermitStatusId`. Exception: the 8 legacy stub Vehicles on PatriotLPR 999000 (Ids 47731-47738) are authorized for DELETE (one-time cleanup, confirmed safe — no FK references, 1 scan in history).
5. **Scope void operations** to rows WE created: `WHERE LicensePlateNumber LIKE 'DEMO%' AND UpdatedById = 'Demo Refresh Script'` (PMS) or `WHERE LicensePlate LIKE 'DEMO%' AND CreatedBy = 'Demo Refresh Script'` (Patriot). Never blanket-void a property.
6. **PMS writes first, then PatriotLPR mirror.** PMS is source of truth.

---

## 3. Architecture — Two Databases, One Property

### PMS (PPOA) — Source of Truth

| Field | Value |
|---|---|
| Database | `PMSMainDb2.0` / `--db pms` |
| Property Name | **Patriot Ridge Apartments** |
| Code | `PLPR-DEMO` |
| PropertyId | *Auto-generated — captured after one-time INSERT* |
| ManagementCompanyId | `16364` (Demo Management Co) |
| TowingCompanyId | `16` (Demo Towing Co) |
| Tables | `Properties`, `PermitTypes`, `Permits` |

### PatriotLPR — Mirror / Mobile App View

| Field | Value |
|---|---|
| Database | `PatriotLPR2.0` / `--db patriot` |
| PropertyId | **999000** (existing — repurposed) |
| CompanyId | **999000** (PatriotLPR Demo Co) |
| IsPPOA | `True` (linked to PMS after one-time setup) |
| PPOAPropertyId | *Same as PMS PropertyId above* |
| Tables | `Properties`, `PermitTypes`, `Vehicles`, `HotlistVehicles` |

### PermitStatus ID Mapping (CRITICAL — different on each side!)

| Status | PMS `PermitStatusId` | PatriotLPR `PermitStatuses.Id` |
|---|---|---|
| Active | **1** | **3** |
| Void | **2** | **4** |

### Self-Signup Flow

New users who sign up via the Patriot LPR mobile app are auto-enrolled into PatriotLPR Company 999000 / Property 999000 by `DemoAccountInitializationService.cs`. After the one-time setup links Property 999000 to PMS, these walk-up users automatically see the demo data on scan.

### Demo Users (Pre-Created, Company 6 "Demo Towing")

These users are on a DIFFERENT PatriotLPR company (6) with a DIFFERENT property (263). They are NOT affected by this guide. For show use, the team can either:
- Let prospects self-sign-up → they land in 999000 → see the demo data
- Hand them a device logged in as `DemoDriver` (Company 6) → uses the separate Property Demo (263/25045) chain

---

## 4. Preflight Check — Has One-Time Setup Been Done?

```sql
-- PMS: check if Patriot Ridge Apartments exists
SELECT PropertyId, Name, Code FROM Properties
WHERE Code = 'PLPR-DEMO';

-- PatriotLPR: check if 999000 is linked
SELECT Id, Name, IsPPOA, PPOAPropertyId FROM Properties
WHERE Id = 999000;
```

**If PMS returns a row AND PatriotLPR shows `IsPPOA=True` with a valid PPOAPropertyId → skip to Part B.**
**If PMS returns 0 rows → run Part A first.**

---

## PART A — One-Time Setup (run once, then never again)

### A1. Create PMS Property

```sql
INSERT INTO Properties
  (Name, Code, Address, City, State, ZipCode,
   NumberOfUnits, PhoneNumber, Email,
   ManagementCompanyId, TowingCompanyId, TimeZoneId,
   IsResidentManagementEnabled, IsUnitLimitRegistrationEnabled,
   IsActiveVisitorLimitEnabled, IsCitationEnforcementEnabled,
   IsUnpaidCitationVisitorBlocked, IsResidentRenewalEmailEnabled,
   IsResidentRenewalEnabled, IsPaidParkingOverrideEnabled,
   IsVisitorPortalAutoRegEnabled, IsRentableSpaceEnabled,
   IsReservedSpaceEnabled, IsResidentSpaceSelfServiceEnabled,
   IsPublicAutoRegEnabled)
VALUES
  ('Patriot Ridge Apartments', 'PLPR-DEMO', '1776 Patriot Dr', 'Dallas', 'Texas', '75201',
   250, '(430) 381-9853', 'sales@ppoagroup.com',
   16364, 16, 'Central Standard Time',
   1, 0,
   0, 0,
   0, 0,
   0, 0,
   1, 0,
   0, 0,
   0);
```

Immediately after:

```sql
SELECT PropertyId, Name, Code FROM Properties WHERE Code = 'PLPR-DEMO';
```

**Note the returned `PropertyId`.** Use it as `@NewPropId` everywhere below.

### A2. Create PMS PermitTypes (10 types)

Replace `@NewPropId` with the actual ID from A1.

```sql
INSERT INTO PermitTypes
  (PropertyId, PermitColorId, PermitDefaultNameId, PermitDuration, TypeName,
   PermitStatusId, IsInvalidRegistrationEnabled, IsPaidParkingEnabled,
   IsTimeLimited, IsDurationPricingEnabled, IsSystemControlledReserve,
   AllowAutoRegistration)
VALUES
  (@NewPropId, 1, 1, 8760, 'Resident',           1, 0, 0, 0, 0, 0, 0),
  (@NewPropId, 2, 2, 8760, 'Reserved',            1, 0, 0, 0, 0, 0, 0),
  (@NewPropId, 3, 3, 8760, 'Carport',             1, 0, 0, 0, 0, 0, 0),
  (@NewPropId, 4, 4, 8760, 'Garage',              1, 0, 0, 0, 0, 0, 0),
  (@NewPropId, 1, 5, 24,   '24Hr Visitor Pass',   1, 0, 0, 0, 0, 0, 0),
  (@NewPropId, 1, 5, 6,    '6Hr Visitor Pass',    1, 0, 0, 0, 0, 0, 0),
  (@NewPropId, 6, 6, 120,  'Temp Pass',           1, 0, 0, 0, 0, 0, 0),
  (@NewPropId, 1, 7, 8760, 'Handicap',            1, 0, 0, 0, 0, 0, 0),
  (@NewPropId, 5, 8, 8760, 'VIP',                 1, 0, 0, 0, 0, 0, 0),
  (@NewPropId, 8, 9, 8760, 'Corporate',           1, 0, 0, 0, 0, 0, 0);
```

Capture the new PermitTypeIds:

```sql
SELECT PermitTypeId, TypeName, PermitDefaultNameId
FROM PermitTypes WHERE PropertyId = @NewPropId
ORDER BY PermitDefaultNameId;
```

### A3. Link PatriotLPR Property 999000 to PMS

```sql
-- PatriotLPR DB (--db patriot)
UPDATE Properties
SET IsPPOA = 1,
    PPOAPropertyId = @NewPropId,
    LastPPOASync = NULL,
    LastModifiedDate = GETUTCDATE(),
    LastModifiedBy = 'Demo Refresh Script'
WHERE Id = 999000;
```

### A4. Create Mirror PermitTypes on PatriotLPR Property 999000

For each PMS PermitType from A2, insert a mirror row in PatriotLPR.PermitTypes. The `PPOAPermitTypeId` column links back to the PMS PermitTypeId.

```sql
-- PatriotLPR DB (--db patriot)
-- Replace @PmsResidentId, @PmsReservedId, etc. with the actual PMS PermitTypeIds from A2
INSERT INTO PermitTypes
  (PropertyId, Name, PermitDefaultNameId, PermitColorId, CustomColor,
   IsActive, DurationHours,
   IsInvalidRegistrationEnabled, InvalidRegistrationLimit, InvalidRegistrationDurationHours,
   IsPPOA, PPOAPermitTypeId,
   CreatedDate, CreatedBy)
VALUES
  (999000, 'Resident',          NULL, 1, NULL, 1, 8760, 0, 0, 0, 1, @PmsResidentId,     GETUTCDATE(), 'Demo Refresh Script'),
  (999000, 'Reserved',          NULL, 2, NULL, 1, 8760, 0, 0, 0, 1, @PmsReservedId,     GETUTCDATE(), 'Demo Refresh Script'),
  (999000, 'Carport',           NULL, 3, NULL, 1, 8760, 0, 0, 0, 1, @PmsCarportId,      GETUTCDATE(), 'Demo Refresh Script'),
  (999000, 'Garage',            NULL, 4, NULL, 1, 8760, 0, 0, 0, 1, @PmsGarageId,       GETUTCDATE(), 'Demo Refresh Script'),
  (999000, '24Hr Visitor Pass', NULL, 1, NULL, 1, 24,   0, 0, 0, 1, @PmsVisitor24Id,    GETUTCDATE(), 'Demo Refresh Script'),
  (999000, '6Hr Visitor Pass',  NULL, 1, NULL, 1, 6,    0, 0, 0, 1, @PmsVisitor6Id,     GETUTCDATE(), 'Demo Refresh Script'),
  (999000, 'Temp Pass',         NULL, 6, NULL, 1, 120,  0, 0, 0, 1, @PmsTempPassId,     GETUTCDATE(), 'Demo Refresh Script'),
  (999000, 'Handicap',          NULL, 1, NULL, 1, 8760, 0, 0, 0, 1, @PmsHandicapId,     GETUTCDATE(), 'Demo Refresh Script'),
  (999000, 'VIP',               NULL, 5, NULL, 1, 8760, 0, 0, 0, 1, @PmsVipId,          GETUTCDATE(), 'Demo Refresh Script'),
  (999000, 'Corporate',         NULL, 8, NULL, 1, 8760, 0, 0, 0, 1, @PmsCorporateId,    GETUTCDATE(), 'Demo Refresh Script');
```

Capture the new Patriot PermitType Ids:

```sql
SELECT Id, Name, PPOAPermitTypeId FROM PermitTypes
WHERE PropertyId = 999000 AND IsPPOA = 1
ORDER BY Id;
```

### A5. Clean up legacy stub Vehicles

These 8 system-seeded stubs (IsPPOA=False, PermitStatusId=NULL) are now obsolete — property is PPOA-backed.

```sql
-- PatriotLPR DB (--db patriot)
DELETE FROM Vehicles
WHERE PropertyId = 999000
  AND Id BETWEEN 47731 AND 47738
  AND CreatedBy = 'System';
```

### A6. Deactivate old non-PPOA PermitTypes

The 3 original non-PPOA types (Ids 1117, 1118, 1119) are no longer needed:

```sql
-- PatriotLPR DB (--db patriot)
UPDATE PermitTypes
SET IsActive = 0,
    LastModifiedDate = GETUTCDATE(),
    LastModifiedBy = 'Demo Refresh Script'
WHERE PropertyId = 999000
  AND IsPPOA = 0
  AND Id IN (1117, 1118, 1119);
```

**End of Part A. Run preflight (§4) to confirm setup is complete before proceeding to Part B.**

---

## PART B — Per-Show Refresh (run before each trade show)

### B0. Compute `SHOW_MID_UTC`

Dalton gives Central time. Central is UTC-5 (DST) or UTC-6 (standard). Second Sunday of March through first Sunday of November = DST.

- Midpoint in Central = `(start + end) / 2`
- Convert to UTC: add 5 hours (DST) or 6 hours (standard)

Example: show 10am-4pm Central (DST) → midpoint 1pm Central → 6pm UTC → `'2026-04-09 18:00:00'`

Store as: `DECLARE @Mid datetime2 = '2026-04-09 18:00:00'` — **show Dalton the computed value for sanity check.**

### B1. Capture Property + PermitType IDs

```sql
-- PMS
SELECT PropertyId FROM Properties WHERE Code = 'PLPR-DEMO';
-- Use this as @PropId

SELECT PermitTypeId, TypeName, PermitDefaultNameId
FROM PermitTypes WHERE PropertyId = @PropId
ORDER BY PermitDefaultNameId;
-- Capture: @ResidentType, @ReservedType, @CarportType, @GarageType,
--          @Visitor24Type, @Visitor6Type, @TempPassType,
--          @HandicapType, @VipType, @CorporateType
```

```sql
-- PatriotLPR — mirror type IDs
SELECT Id AS PatriotTypeId, Name, PPOAPermitTypeId
FROM PermitTypes
WHERE PropertyId = 999000 AND IsPPOA = 1 AND IsActive = 1
ORDER BY Id;
```

### B2. Void previous demo permits (PMS)

Only touches rows WE created — never blanket-voids.

```sql
-- PMS (--db pms)
-- Preview first:
SELECT COUNT(*) AS WouldVoid FROM Permits
WHERE PropertyId = @PropId
  AND LicensePlateNumber LIKE 'DEMO%'
  AND UpdatedById = 'Demo Refresh Script'
  AND PermitStatusId = 1;

-- Then execute:
UPDATE Permits
SET PermitStatusId = 2,
    LastUpdatedBy = 'Demo Refresh Script',
    PermitUpdatedDate = GETUTCDATE()
WHERE PropertyId = @PropId
  AND LicensePlateNumber LIKE 'DEMO%'
  AND UpdatedById = 'Demo Refresh Script'
  AND PermitStatusId = 1;
```

### B3. Void previous demo Vehicles (PatriotLPR mirror)

```sql
-- PatriotLPR (--db patriot)
UPDATE Vehicles
SET PermitStatusId = 4,
    LastModifiedDate = GETUTCDATE(),
    LastModifiedBy = 'Demo Refresh Script'
WHERE PropertyId = 999000
  AND LicensePlate LIKE 'DEMO%'
  AND CreatedBy = 'Demo Refresh Script'
  AND PermitStatusId = 3;
```

### B4. Insert fresh PMS Permits (show-time anchored)

Replace `@Mid` with the UTC midpoint from B0. Replace `@ResidentType`, etc. with the PMS PermitTypeIds from B1.

#### Scenario Matrix

| # | Plate | Scenario | PMS PermitTypeId var | PMS StatusId | Expiration |
|---|---|---|---|---|---|
| 1 | DEMO001 | Valid Resident | @ResidentType | 1 | Mid + 30d |
| 2 | DEMO002 | Valid Resident | @ResidentType | 1 | Mid + 30d |
| 3 | DEMO003 | Expired Resident | @ResidentType | 1 | Mid - 7d |
| 4 | DEMO004 | Voided Resident | @ResidentType | 2 | Mid + 365d |
| 5 | DEMO005 | Reserved | @ReservedType | 1 | Mid + 60d |
| 6 | DEMO006 | Carport | @CarportType | 1 | Mid + 60d |
| 7 | DEMO007 | VIP | @VipType | 1 | Mid + 180d |
| 8 | DEMO008 | Visitor valid (+18h) | @Visitor24Type | 1 | Mid + 18h |
| 9 | DEMO009 | Visitor ~6h | @Visitor6Type | 1 | Mid + 6h |
| 10 | DEMO010 | Visitor ~3h | @Visitor6Type | 1 | Mid + 3h |
| 11 | DEMO011 | Expired Visitor | @Visitor24Type | 1 | Mid - 2h |
| 12 | DEMO012 | Voided Visitor | @Visitor24Type | 2 | Mid + 12h |
| 13 | DEMO013 | Hotlist (Patriot only) | n/a | n/a | n/a |
| 14 | DEMO014 | Unknown plate (nowhere) | n/a | n/a | n/a |

```sql
-- PMS (--db pms)
DECLARE @Mid datetime2 = '2026-04-09 18:00:00';  -- EDIT PER SHOW
DECLARE @Prop int = (SELECT PropertyId FROM Properties WHERE Code = 'PLPR-DEMO');
DECLARE @Res int = (SELECT TOP 1 PermitTypeId FROM PermitTypes WHERE PropertyId = @Prop AND PermitDefaultNameId = 1 AND TypeName = 'Resident');
DECLARE @Rsv int = (SELECT TOP 1 PermitTypeId FROM PermitTypes WHERE PropertyId = @Prop AND PermitDefaultNameId = 2);
DECLARE @Cpt int = (SELECT TOP 1 PermitTypeId FROM PermitTypes WHERE PropertyId = @Prop AND PermitDefaultNameId = 3);
DECLARE @V24 int = (SELECT TOP 1 PermitTypeId FROM PermitTypes WHERE PropertyId = @Prop AND PermitDefaultNameId = 5 AND TypeName = '24Hr Visitor Pass');
DECLARE @V06 int = (SELECT TOP 1 PermitTypeId FROM PermitTypes WHERE PropertyId = @Prop AND PermitDefaultNameId = 5 AND TypeName = '6Hr Visitor Pass');
DECLARE @Vip int = (SELECT TOP 1 PermitTypeId FROM PermitTypes WHERE PropertyId = @Prop AND PermitDefaultNameId = 8);

INSERT INTO Permits
  (CreateDate, PropertyId, PermitTypeId, PermitColorId, PermitDuration,
   ExpirationDate, FirstName, LastName,
   ResidentVisiting, ApartmentVisiting, AssignedSpace,
   VehicleYear, VehicleMake, VehicleModel, VehicleColor,
   LicensePlateNumber, LicensePlateState, PermitStatusId,
   PrintAttempts, UpdatedById, WasPaidParking)
VALUES
-- 1. Valid Resident
(GETUTCDATE(), @Prop, @Res, 1, 8760, DATEADD(DAY,30,@Mid), 'Alex','Johnson', 'Alex Johnson','101',NULL, '2022','Honda','Civic','Silver', 'DEMO001','TX', 1, 0,'Demo Refresh Script',0),
-- 2. Valid Resident
(GETUTCDATE(), @Prop, @Res, 1, 8760, DATEADD(DAY,30,@Mid), 'Sam','Martinez', 'Sam Martinez','102',NULL, '2021','Toyota','Corolla','White', 'DEMO002','TX', 1, 0,'Demo Refresh Script',0),
-- 3. Expired Resident (Active status, past date)
(DATEADD(DAY,-400,@Mid), @Prop, @Res, 1, 8760, DATEADD(DAY,-7,@Mid), 'Jordan','Lee', 'Jordan Lee','103',NULL, '2019','Ford','Focus','Blue', 'DEMO003','TX', 1, 0,'Demo Refresh Script',0),
-- 4. Voided Resident
(GETUTCDATE(), @Prop, @Res, 1, 8760, DATEADD(DAY,365,@Mid), 'Taylor','Reed', 'Taylor Reed','104',NULL, '2020','Nissan','Altima','Black', 'DEMO004','TX', 2, 0,'Demo Refresh Script',0),
-- 5. Reserved (assigned space)
(GETUTCDATE(), @Prop, @Rsv, 2, 8760, DATEADD(DAY,60,@Mid), 'Morgan','Chen', 'Morgan Chen','105','R-12', '2023','Tesla','Model 3','Red', 'DEMO005','TX', 1, 0,'Demo Refresh Script',0),
-- 6. Carport
(GETUTCDATE(), @Prop, @Cpt, 3, 8760, DATEADD(DAY,60,@Mid), 'Riley','Walker', 'Riley Walker','106','C-04', '2022','Chevy','Tahoe','Gray', 'DEMO006','TX', 1, 0,'Demo Refresh Script',0),
-- 7. VIP
(GETUTCDATE(), @Prop, @Vip, 5, 8760, DATEADD(DAY,180,@Mid), 'Casey','Brooks', 'Casey Brooks','PH1','V-01', '2024','Lexus','LX','White', 'DEMO007','TX', 1, 0,'Demo Refresh Script',0),
-- 8. Visitor valid (+18h)
(DATEADD(HOUR,-6,@Mid), @Prop, @V24, 1, 24, DATEADD(HOUR,18,@Mid), 'Avery','Shah', 'Alex Johnson','101',NULL, '2022','Mazda','CX-5','Blue', 'DEMO008','TX', 1, 0,'Demo Refresh Script',0),
-- 9. Visitor ~6h
(DATEADD(HOUR,-18,@Mid), @Prop, @V06, 1, 6, DATEADD(HOUR,6,@Mid), 'Quinn','Rivera', 'Sam Martinez','102',NULL, '2021','Kia','Sorento','Black', 'DEMO009','TX', 1, 0,'Demo Refresh Script',0),
-- 10. Visitor ~3h
(DATEADD(HOUR,-21,@Mid), @Prop, @V06, 1, 6, DATEADD(HOUR,3,@Mid), 'Drew','Patel', 'Jordan Lee','103',NULL, '2020','Hyundai','Elantra','Silver', 'DEMO010','TX', 1, 0,'Demo Refresh Script',0),
-- 11. Expired Visitor
(DATEADD(HOUR,-26,@Mid), @Prop, @V24, 1, 24, DATEADD(HOUR,-2,@Mid), 'Skyler','Nguyen', 'Morgan Chen','105',NULL, '2018','Jeep','Wrangler','Green', 'DEMO011','TX', 1, 0,'Demo Refresh Script',0),
-- 12. Voided Visitor
(DATEADD(HOUR,-12,@Mid), @Prop, @V24, 1, 24, DATEADD(HOUR,12,@Mid), 'Logan','Kim', 'Taylor Reed','104',NULL, '2019','Subaru','Outback','Brown', 'DEMO012','TX', 2, 0,'Demo Refresh Script',0);
```

### B5. Capture PMS PermitIds for the mirror

```sql
-- PMS (--db pms)
SELECT PermitId, LicensePlateNumber, PermitStatusId, ExpirationDate
FROM Permits
WHERE PropertyId = @Prop
  AND LicensePlateNumber LIKE 'DEMO%'
  AND UpdatedById = 'Demo Refresh Script'
  AND PermitStatusId IN (1, 2)
ORDER BY LicensePlateNumber;
```

### B6. Insert mirror Vehicles in PatriotLPR

For EACH PMS Permit from B5, insert a matching Vehicle row. Map PMS StatusId → Patriot StatusId (1→3, 2→4). Link via `PPOAPermitId`.

```sql
-- PatriotLPR (--db patriot)
-- Replace @PmsPermitId_N, @PatriotTypeId_N with actual values from B5/B1
-- Replace @Mid with same UTC midpoint

INSERT INTO Vehicles
  (LicensePlate, State, VehicleMake, VehicleModel, VehicleColor, VehicleYear,
   PropertyId, PermitTypeId, AssignedSpace, ExpirationDate, PermitStatusId,
   IsPPOA, PPOAPermitId,
   CreatedDate, CreatedBy)
VALUES
('DEMO001','TX','Honda','Civic','Silver','2022',       999000, @PatriotResidentTypeId, NULL, DATEADD(DAY,30,@Mid),  3, 1, @PmsPermitId_1, GETUTCDATE(), 'Demo Refresh Script'),
('DEMO002','TX','Toyota','Corolla','White','2021',     999000, @PatriotResidentTypeId, NULL, DATEADD(DAY,30,@Mid),  3, 1, @PmsPermitId_2, GETUTCDATE(), 'Demo Refresh Script'),
('DEMO003','TX','Ford','Focus','Blue','2019',          999000, @PatriotResidentTypeId, NULL, DATEADD(DAY,-7,@Mid),  3, 1, @PmsPermitId_3, GETUTCDATE(), 'Demo Refresh Script'),
('DEMO004','TX','Nissan','Altima','Black','2020',      999000, @PatriotResidentTypeId, NULL, DATEADD(DAY,365,@Mid), 4, 1, @PmsPermitId_4, GETUTCDATE(), 'Demo Refresh Script'),
('DEMO005','TX','Tesla','Model 3','Red','2023',        999000, @PatriotReservedTypeId, 'R-12', DATEADD(DAY,60,@Mid),  3, 1, @PmsPermitId_5, GETUTCDATE(), 'Demo Refresh Script'),
('DEMO006','TX','Chevy','Tahoe','Gray','2022',         999000, @PatriotCarportTypeId, 'C-04', DATEADD(DAY,60,@Mid),  3, 1, @PmsPermitId_6, GETUTCDATE(), 'Demo Refresh Script'),
('DEMO007','TX','Lexus','LX','White','2024',           999000, @PatriotVipTypeId,     'V-01', DATEADD(DAY,180,@Mid), 3, 1, @PmsPermitId_7, GETUTCDATE(), 'Demo Refresh Script'),
('DEMO008','TX','Mazda','CX-5','Blue','2022',          999000, @PatriotVisitor24TypeId, NULL, DATEADD(HOUR,18,@Mid), 3, 1, @PmsPermitId_8, GETUTCDATE(), 'Demo Refresh Script'),
('DEMO009','TX','Kia','Sorento','Black','2021',        999000, @PatriotVisitor6TypeId,  NULL, DATEADD(HOUR,6,@Mid),  3, 1, @PmsPermitId_9, GETUTCDATE(), 'Demo Refresh Script'),
('DEMO010','TX','Hyundai','Elantra','Silver','2020',   999000, @PatriotVisitor6TypeId,  NULL, DATEADD(HOUR,3,@Mid),  3, 1, @PmsPermitId_10, GETUTCDATE(), 'Demo Refresh Script'),
('DEMO011','TX','Jeep','Wrangler','Green','2018',      999000, @PatriotVisitor24TypeId, NULL, DATEADD(HOUR,-2,@Mid), 3, 1, @PmsPermitId_11, GETUTCDATE(), 'Demo Refresh Script'),
('DEMO012','TX','Subaru','Outback','Brown','2019',     999000, @PatriotVisitor24TypeId, NULL, DATEADD(HOUR,12,@Mid), 4, 1, @PmsPermitId_12, GETUTCDATE(), 'Demo Refresh Script');
```

### B7. HotlistVehicle (Patriot only — no PMS equivalent)

```sql
-- PatriotLPR (--db patriot)
-- Only insert if not already there
IF NOT EXISTS (SELECT 1 FROM HotlistVehicles WHERE LicensePlate = 'DEMO013' AND PropertyId = 999000)
INSERT INTO HotlistVehicles
  (LicensePlate, State, VIN, Year, Make, Model, Color,
   PropertyId, CompanyId, AlertReason, CaseNumber,
   IsActive, CreatedDate, CreatedBy, LastModifiedDate, LastModifiedBy)
VALUES
  ('DEMO013', 'TX', NULL, '2017', 'Dodge', 'Ram', 'Red',
   999000, 999000, 'Repeat trespasser - flagged for tow on sight', 'DEMO-CASE-001',
   1, GETUTCDATE(), 'Demo Refresh Script', GETUTCDATE(), 'Demo Refresh Script');
```

`DEMO014` is intentionally NOT inserted anywhere — it's the "unknown plate / no permit on file" scenario.

### B8. Verify both sides match

```sql
-- PMS verification
SELECT LicensePlateNumber, pt.TypeName,
       ps.Status, p.ExpirationDate,
       DATEDIFF(HOUR, GETUTCDATE(), p.ExpirationDate) AS HoursLeft
FROM Permits p
JOIN PermitTypes pt ON p.PermitTypeId = pt.PermitTypeId
JOIN PermitStatuses ps ON p.PermitStatusId = ps.PermitStatusId
WHERE p.PropertyId = (SELECT PropertyId FROM Properties WHERE Code = 'PLPR-DEMO')
  AND p.LicensePlateNumber LIKE 'DEMO%'
  AND p.UpdatedById = 'Demo Refresh Script'
  AND p.PermitStatusId IN (1, 2)
ORDER BY p.LicensePlateNumber;

-- PatriotLPR verification
SELECT v.LicensePlate, pt.Name AS TypeName,
       ps.Name AS Status, v.ExpirationDate,
       DATEDIFF(HOUR, GETUTCDATE(), v.ExpirationDate) AS HoursLeft
FROM Vehicles v
LEFT JOIN PermitTypes pt ON v.PermitTypeId = pt.Id
LEFT JOIN PermitStatuses ps ON v.PermitStatusId = ps.Id
WHERE v.PropertyId = 999000
  AND v.LicensePlate LIKE 'DEMO%'
  AND v.CreatedBy = 'Demo Refresh Script'
ORDER BY v.LicensePlate;
```

Confirm both sides show the same 12 plates with matching types, statuses, and expirations.

### B9. Write plate_list.txt

Overwrite `C:\Users\Dalton\source\repos\daltonloomis0818\LPRTestBench\data\plate_list.txt`:

```
DEMO001
DEMO002
DEMO003
DEMO004
DEMO005
DEMO006
DEMO007
DEMO008
DEMO009
DEMO010
DEMO011
DEMO012
DEMO013
DEMO014
```

### B10. Present summary to Dalton

Show the combined summary in Central time (convert UTC back):

| Plate | Scenario | Type | Status | Expires (Central) | Where |
|---|---|---|---|---|---|
| DEMO001 | Valid Resident | Resident | Active | Mid + 30d | PMS + Patriot |
| DEMO002 | Valid Resident | Resident | Active | Mid + 30d | PMS + Patriot |
| DEMO003 | Expired Resident | Resident | Active (date passed) | Mid - 7d | PMS + Patriot |
| DEMO004 | Voided Resident | Resident | Void | Mid + 365d | PMS + Patriot |
| DEMO005 | Reserved | Reserved | Active | Mid + 60d | PMS + Patriot |
| DEMO006 | Carport | Carport | Active | Mid + 60d | PMS + Patriot |
| DEMO007 | VIP | VIP | Active | Mid + 180d | PMS + Patriot |
| DEMO008 | Visitor valid | 24Hr Visitor | Active | Mid + 18h | PMS + Patriot |
| DEMO009 | Visitor ~6h | 6Hr Visitor | Active | Mid + 6h | PMS + Patriot |
| DEMO010 | Visitor ~3h | 6Hr Visitor | Active | Mid + 3h | PMS + Patriot |
| DEMO011 | Expired Visitor | 24Hr Visitor | Active (date passed) | Mid - 2h | PMS + Patriot |
| DEMO012 | Voided Visitor | 24Hr Visitor | Void | Mid + 12h | PMS + Patriot |
| DEMO013 | Hotlist | - | - | - | **Patriot only** |
| DEMO014 | Unknown plate | - | - | - | **Nowhere** |

---

## 5. Reference Enums

### PMS `PermitDefaultNames`

| Id | Name |
|---|---|
| 1 | Resident |
| 2 | Reserved |
| 3 | Carport |
| 4 | Garage |
| 5 | Visitor |
| 6 | Temp Pass |
| 7 | Handicap |
| 8 | VIP |
| 9 | Corporate |

### PMS `PermitStatuses` — 1=Active, 2=Void, 3=Pending
### PatriotLPR `PermitStatuses` — 3=Active, 4=Void

### PMS `PermitColors`

| Id | Color |
|---|---|
| 1 | Permit-Less |
| 2 | Red |
| 3 | Green |
| 4 | Yellow |
| 5 | Blue |
| 6 | Pink |
| 7 | Purple |
| 8 | Orange |

---

## 6. Safety / Abort Triggers

Abort and escalate to Dalton if:

- Preflight returns wrong property name or code for the expected PropertyId.
- Any query plan touches a PropertyId other than Patriot Ridge's PMS Id or PatriotLPR 999000.
- Void rowcount is unexpectedly high (>50 for a demo property).
- A `DELETE` appears anywhere outside the one-time stub cleanup (A5).
- The AzureQuery auth token fails — tell Dalton to re-auth in the browser.

---

## 7. Quick Commands

```bash
# PMS
dotnet run --project "C:\Users\Dalton\source\repos\daltonloomis0818\AzureQuery\AzureQuery.csproj" -- --db pms "YOUR SQL"

# PatriotLPR
dotnet run --project "C:\Users\Dalton\source\repos\daltonloomis0818\AzureQuery\AzureQuery.csproj" -- --db patriot "YOUR SQL"

# LPRTestBench
cd C:\Users\Dalton\source\repos\daltonloomis0818\LPRTestBench && python main.py
```

---

## 8. Trigger Phrases

- "Refresh demo data, show today 10am-4pm Central"
- "Trade show refresh - window is X to Y Central"
- "Live plate data refresh"

Only required input: **the show window in Central time.** Everything else comes from this guide.
