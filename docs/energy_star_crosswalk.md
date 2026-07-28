# ENERGY STAR Building Type Crosswalk

This file mirrors `src/buildstock_processor/energy_star_crosswalk.json` in a Markdown format that is easy for people and simple tools to parse. The Python API exposes the same data through `energy_star_crosswalk()`, `map_energy_star_property_type()`, and `energy_star_property_types_for_buildstock_type()`.

This is a best-effort crosswalk authored for buildstock_processor, **not** an official NLR or EPA publication. ENERGY STAR Portfolio Manager's property types are far more granular (and organized differently) than BuildStock's building types, which come from DOE's commercial prototype building models (ComStock) and simplified residential housing categories (ResStock). Several ENERGY STAR property types have no close BuildStock equivalent at all -- those rows have match_quality = unmapped and empty product/building-type columns.

- Total ENERGY STAR property types: 84
- exact matches: 13
- approximate matches: 65
- unmapped matches: 6

| ENERGY STAR Property Type | BuildStock Product | BuildStock Building Type | Match Quality | Notes |
| --- | --- | --- | --- | --- |
| Adult Education | comstock | SecondarySchool | approximate | Adult-education classroom space modeled on ComStock's secondary-school prototype; no dedicated adult-education building type exists. |
| Ambulatory Surgical Center | comstock | Outpatient | approximate | Outpatient surgical care is close to ComStock's outpatient healthcare prototype, though surgical centers have higher plug/HVAC loads. |
| Bank Branch | comstock | SmallOffice | approximate | Small commercial office/teller space; ComStock has no dedicated bank prototype. |
| Bar/Nightclub | comstock | FullServiceRestaurant | approximate | Food/beverage service with extended evening hours; closest match is the full-service restaurant prototype. |
| Barracks | resstock | Multi-Family with 5+ Units | approximate | Military barracks are dormitory-style multi-occupant housing, closest to ResStock's larger multifamily category. |
| Bowling Alley | comstock | RetailStandalone | approximate | Large single-story recreational space; no bowling/entertainment prototype exists in ComStock. |
| Casino | comstock | RetailStandalone | approximate | Large open-plan gaming floor; no casino prototype exists, so the standalone-retail prototype is used as a rough proxy. |
| College/University | comstock | SecondarySchool | approximate | ComStock has no higher-education prototype; the secondary-school prototype is the closest available large academic building. |
| Convenience Store with Gas Station | comstock | RetailStandalone | approximate | Small-format retail; ComStock has no convenience-store-with-fuel prototype. |
| Convenience Store without Gas Station | comstock | RetailStandalone | approximate | Small-format retail store. |
| Convention Center | comstock | RetailStandalone | approximate | Large open-plan assembly space; no convention-center prototype exists in ComStock. |
| Courthouse | comstock | MediumOffice | approximate | Government office/administrative building; no courthouse-specific prototype exists. |
| Data Center | comstock | Warehouse | approximate | No data-center prototype exists in ComStock; actual data centers have far higher plug/cooling loads than the warehouse prototype implies. |
| Distribution Center | comstock | Warehouse | exact | Distribution centers are warehouses. |
| Drinking Water Treatment & Distribution | comstock | Warehouse | approximate | Industrial/utility building with no dedicated ComStock prototype. |
| Enclosed Mall | comstock | RetailStripmall | approximate | ComStock's strip-mall prototype is the closest available retail-complex type; enclosed malls are typically larger and centrally conditioned. |
| Energy/Power Station | comstock | Warehouse | approximate | Industrial/utility building with no dedicated ComStock prototype. |
| Fast Food Restaurant | comstock | QuickServiceRestaurant | exact | Direct match to ComStock's quick-service restaurant prototype. |
| Financial Office | comstock | SmallOffice | approximate | Small commercial office space. |
| Fire Station | comstock | SmallOffice | approximate | Small institutional/office-like building; no fire-station prototype exists. |
| Fitness Center/Health Club/Gym | comstock | RetailStandalone | approximate | Large open-plan recreational retail space; no gym prototype exists. |
| Food Sales | comstock | Grocery | approximate | General food-retail category; closest match is ComStock's grocery prototype. |
| Food Service | comstock | FullServiceRestaurant | approximate | General food-service category; closest match is ComStock's full-service restaurant prototype. |
| Hospital (General Medical & Surgical) | comstock | Hospital | exact | Direct match to ComStock's hospital prototype. |
| Hotel | comstock | SmallHotel | approximate | Generic hotel type with no size/service-level indicator; SmallHotel (limited-service) represents the majority of the US hotel stock by count. Use LargeHotel for known full-service/larger properties. |
| Ice/Curling Rink | comstock | Warehouse | approximate | Large single-volume specialized recreational space; no rink prototype exists. |
| Indoor Arena | comstock | Warehouse | approximate | Large single-volume assembly space; no arena prototype exists. |
| K-12 School | comstock | PrimarySchool | approximate | Generic K-12 designation spans both ComStock's primary- and secondary-school prototypes; PrimarySchool is used as the default. Use SecondarySchool for known middle/high schools. |
| Laboratory | comstock | LargeOffice | approximate | High plug-load research space; ComStock has no laboratory prototype, so the large-office prototype is used as a rough proxy. |
| Library | comstock | MediumOffice | approximate | Public institutional building with reading rooms and staff offices; no library prototype exists in ComStock. |
| Lifestyle Center | comstock | RetailStripmall | approximate | Open-air, multi-tenant retail complex; closest match is ComStock's strip-mall prototype. |
| Mailing Center/Post Office | comstock | SmallOffice | approximate | Small commercial service building. |
| Manufacturing/Industrial Plant | comstock | Warehouse | approximate | No manufacturing/industrial prototype exists in ComStock; actual process loads can differ substantially from the warehouse prototype. |
| Medical Office | comstock | Outpatient | approximate | Medical offices are effectively outpatient clinics. |
| Mixed Use Property | comstock | MediumOffice | approximate | No mixed-use prototype exists; MediumOffice is used as a generic default anchor use. Prefer mapping the property's dominant use directly when known. |
| Movie Theater | comstock | RetailStandalone | approximate | Large open-plan entertainment retail space; no theater prototype exists. |
| Multifamily Housing | resstock | Multi-Family with 5+ Units | exact | ENERGY STAR's multifamily housing property type is designed for buildings with 5+ residential units, matching ResStock's category directly. |
| Museum | comstock | RetailStandalone | approximate | Public assembly/exhibition space; no museum prototype exists. |
| Non-Refrigerated Warehouse | comstock | Warehouse | exact | Direct match to ComStock's warehouse prototype. |
| Office | comstock | MediumOffice | approximate | Generic office type with no size indicator; MediumOffice is used as the default. Use SmallOffice/LargeOffice when building size is known. |
| Other |  |  | unmapped | Generic catch-all category with no identifiable building use. |
| Other - Education | comstock | SecondarySchool | approximate | Generic education catch-all; closest match is ComStock's secondary-school prototype. |
| Other - Entertainment/Public Assembly | comstock | RetailStandalone | approximate | Generic entertainment/assembly catch-all with no dedicated ComStock prototype. |
| Other - Lodging/Residential | resstock | Multi-Family with 5+ Units | approximate | Generic lodging/residential catch-all; mapped to ResStock's multifamily category as a residential-leaning default. |
| Other - Public Service | comstock | SmallOffice | approximate | Generic public-service catch-all; closest match is a small office/administrative building. |
| Other - Recreation | comstock | RetailStandalone | approximate | Generic recreation catch-all with no dedicated ComStock prototype. |
| Other - Restaurant/Bar | comstock | FullServiceRestaurant | approximate | Generic food/beverage catch-all; closest match is ComStock's full-service restaurant prototype. |
| Other - Retail/Mall | comstock | RetailStripmall | approximate | Generic retail catch-all; closest match is ComStock's strip-mall prototype. |
| Other - Services | comstock | SmallOffice | approximate | Generic services catch-all; closest match is a small office/commercial-service building. |
| Other - Specialty Hospital | comstock | Hospital | approximate | Specialty hospitals share ComStock's general hospital prototype's 24/7 institutional occupancy pattern. |
| Other - Stadium |  |  | unmapped | Open-air or semi-conditioned assembly structure with no representative ComStock prototype. |
| Other - Technology/Science | comstock | LargeOffice | approximate | High plug-load office/lab hybrid; closest match is ComStock's large-office prototype. |
| Other - Utility | comstock | Warehouse | approximate | Generic utility/industrial catch-all with no dedicated ComStock prototype. |
| Outpatient Rehabilitation/Physical Therapy | comstock | Outpatient | exact | Direct match to ComStock's outpatient healthcare prototype. |
| Parking |  |  | unmapped | Unconditioned parking structures aren't represented by any ComStock or ResStock building type. |
| Performing Arts | comstock | RetailStandalone | approximate | Public assembly/auditorium space; no performing-arts prototype exists. |
| Personal Services (Health/Beauty, Dry Cleaning, etc) | comstock | RetailStripmall | approximate | Small service-retail space typically found in strip-mall-style buildings. |
| Police Station | comstock | SmallOffice | approximate | Small institutional/office-like building; no police-station prototype exists. |
| Pre-school/Daycare | comstock | PrimarySchool | approximate | Early-childhood instructional space; closest match is ComStock's primary-school prototype. |
| Prison/Incarceration | comstock | Hospital | approximate | 24/7 institutional occupancy with high security and continuous operation, similar in schedule/load pattern to ComStock's hospital prototype; no detention-facility prototype exists. |
| Refrigerated Warehouse | comstock | Warehouse | approximate | ComStock's single warehouse prototype doesn't model refrigeration loads, which are substantial for this property type. |
| Repair Services (Vehicle, Shoe, Locksmith, etc.) | comstock | RetailStripmall | approximate | Small service-retail space typically found in strip-mall-style buildings. |
| Residence Hall/Dormitory | resstock | Multi-Family with 5+ Units | approximate | Dormitories are multi-occupant residential buildings, closest to ResStock's larger multifamily category. |
| Residential Care Facility | comstock | Hospital | approximate | 24/7 medical/custodial care occupancy pattern, similar to ComStock's hospital prototype; no dedicated residential-care prototype exists. |
| Restaurant | comstock | FullServiceRestaurant | exact | Direct match to ComStock's full-service restaurant prototype. |
| Retail Store | comstock | RetailStandalone | exact | Direct match to ComStock's standalone-retail prototype. |
| Self-Storage Facility | comstock | Warehouse | exact | Low-load storage building, matching ComStock's warehouse prototype well. |
| Senior Living Community | resstock | Multi-Family with 5+ Units | approximate | Congregate residential housing, closest to ResStock's larger multifamily category; does not capture assisted-living-specific loads. |
| Single Family Home | resstock | Single-Family Detached | exact | Direct match to ResStock's single-family detached category. |
| Social/Meeting Hall | comstock | RetailStandalone | approximate | Public assembly space; no meeting-hall prototype exists. |
| Stadium (Closed) | comstock | Warehouse | approximate | Large enclosed single-volume assembly space; no stadium prototype exists in ComStock. |
| Stadium (Open) |  |  | unmapped | Open-air structure not represented by any conditioned ComStock or ResStock building type. |
| Strip Mall | comstock | RetailStripmall | exact | Direct match to ComStock's strip-mall prototype. |
| Supermarket/Grocery Store | comstock | Grocery | exact | Direct match to ComStock's grocery prototype. |
| Swimming Pool |  |  | unmapped | Specialized aquatic facility not represented by any ComStock or ResStock building type. |
| Transportation Terminal/Station | comstock | RetailStandalone | approximate | Large open-plan public circulation space; no terminal/station prototype exists. |
| Urgent Care/Clinic/Other Outpatient | comstock | Outpatient | exact | Direct match to ComStock's outpatient healthcare prototype. |
| Vehicle Dealership | comstock | RetailStandalone | approximate | Showroom retail space; no dealership prototype exists. |
| Veterinary Office | comstock | Outpatient | approximate | Clinic-style medical office, closest to ComStock's outpatient prototype. |
| Vocational School | comstock | SecondarySchool | approximate | Trade/vocational instructional space; closest match is ComStock's secondary-school prototype. |
| Wastewater Treatment Plant | comstock | Warehouse | approximate | Industrial/utility building with no dedicated ComStock prototype. |
| Wholesale Club/Supercenter | comstock | Grocery | approximate | Large-format grocery/general-merchandise store; closest match is ComStock's grocery prototype, though supercenters are typically larger. |
| Worship Facility | comstock | RetailStandalone | approximate | Large open-plan assembly space; no worship-facility prototype exists in ComStock. |
| Zoo |  |  | unmapped | Primarily outdoor specialized facility not represented by any ComStock or ResStock building type. |
