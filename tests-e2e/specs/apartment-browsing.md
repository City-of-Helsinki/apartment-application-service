# Apartment Browsing Test Plan

**Site**: http://localhost:18080  
**Scope**: Browsing right-of-occupancy (asumisoikeus/Haso) and ownership (omistus/Hitas) apartment listings.  
**Backend**: Django apartment-application-service at http://localhost:18081 provides apartment data.  
**Assumptions**: Fresh browser session, no prior authentication. Fixture data has been loaded into Django — some apartments may be present. Drupal is configured to fetch apartment data from the Django backend.

---

## Test Scenario 1: Right-of-Occupancy Listing Page Loads

**Title**: Haso (right-of-occupancy) apartment listing page renders  
**Starting state**: Browser navigated to `http://localhost:18080/fi`

### Steps

1. Navigate to `http://localhost:18080/fi`
2. Find a navigation link or section related to right-of-occupancy apartments  
   (Finnish: "asumisoikeus", "Haso", or similar)
3. Click the link
4. Verify the URL navigates to the correct listing path (e.g. `/fi/asumisoikeusasunnot` or `/fi/haso`)
5. Verify the page title or heading contains the relevant term ("asumisoikeus", "Haso")
6. Verify the page does not show a 404 or server error

**Expected outcome**: Right-of-occupancy listing page is accessible from the main navigation.  
**Success criteria**: Page loads with HTTP 200, correct heading found.  
**Failure conditions**: No link to Haso apartments found, page returns error.

---

## Test Scenario 2: Haso Listing Shows Apartment Cards

**Title**: Haso listing displays apartment project cards with key information  
**Starting state**: Haso apartment listing page is loaded

### Steps

1. Navigate to the Haso apartment listing page
2. Verify that apartment project cards or list items are present
3. For each visible card, verify it contains at least:
   - A project name or title
   - A neighborhood or district name
4. Verify that at least one card is visible (assuming fixture data includes Haso apartments)
5. Verify the cards are not overlapping or visually broken

**Expected outcome**: Listing shows apartment project cards with names and locations.  
**Success criteria**: At least one card found, card contains title and district.  
**Failure conditions**: No cards present when fixture data is loaded, cards missing title/location.

---

## Test Scenario 3: Haso Apartment Detail Page Opens

**Title**: Clicking a Haso apartment card opens its detail page  
**Starting state**: Haso apartment listing page with at least one card visible

### Steps

1. Navigate to the Haso apartment listing page
2. Locate the first apartment project card
3. Click on the card (or a "Lue lisää" / "Read more" link within it)
4. Verify the URL changes to a project-specific path
5. Verify the detail page loads without error
6. Verify the project name heading is present on the detail page
7. Verify the page contains apartment-specific details (address, apartment types, or pricing)

**Expected outcome**: Detail page opens with project-specific information.  
**Success criteria**: URL changes, detail page loads, project heading present.  
**Failure conditions**: Click does not navigate, detail page returns 404, page blank.

---

## Test Scenario 4: Haso Detail Page Shows Apartment Information

**Title**: Haso apartment detail page displays relevant housing information  
**Starting state**: A Haso project detail page is open

### Steps

1. Navigate to a Haso apartment detail page
2. Verify at least one of the following is present:
   - Address or location information
   - Number of apartments or apartment sizes
   - Estimated price range or financing cost
   - Application period or availability status
3. Verify there are no broken image placeholders (alt text showing instead of image)
4. Verify the page header and navigation are still visible

**Expected outcome**: Detail page shows substantive apartment information.  
**Success criteria**: At least one data field (address, price, or count) found.  
**Failure conditions**: Detail page contains no apartment-specific data, only generic content.

---

## Test Scenario 5: Ownership Apartment Listing Page Loads

**Title**: Hitas/omistus (ownership) apartment listing page renders  
**Starting state**: Browser navigated to `http://localhost:18080/fi`

### Steps

1. Navigate to `http://localhost:18080/fi`
2. Find a navigation link or section related to ownership apartments  
   (Finnish: "omistusasunnot", "Hitas", or similar)
3. Click the link
4. Verify the URL navigates to the correct listing path (e.g. `/fi/omistusasunnot` or `/fi/hitas`)
5. Verify the page title or heading contains a relevant term ("omistus", "Hitas")
6. Verify the page does not show a 404 or server error

**Expected outcome**: Ownership apartment listing page is accessible from the main navigation.  
**Success criteria**: Page loads with HTTP 200, correct heading found.  
**Failure conditions**: No link to ownership apartments found, page returns error.

---

## Test Scenario 6: Hitas Listing Shows Apartment Cards

**Title**: Hitas listing displays apartment project cards  
**Starting state**: Hitas/ownership apartment listing page is loaded

### Steps

1. Navigate to the Hitas ownership apartment listing page
2. Verify that apartment project cards or list items are present
3. For each visible card, verify it contains at least a project name
4. Verify the card type or label distinguishes ownership from right-of-occupancy  
   (e.g. "Hitas", "omistus", or a visual badge)

**Expected outcome**: Listing shows ownership apartment cards with appropriate labels.  
**Success criteria**: At least one card found with a name, ownership type indicated.  
**Failure conditions**: No cards found, cards show no type distinction.

---

## Test Scenario 7: Hitas Detail Page Opens from Listing

**Title**: Clicking a Hitas apartment card opens its detail page  
**Starting state**: Hitas apartment listing page with at least one card visible

### Steps

1. Navigate to the Hitas ownership apartment listing page
2. Locate the first apartment project card
3. Click on the card or its primary link
4. Verify the URL changes to a project-specific path
5. Verify the detail page loads without error
6. Verify the project name heading matches the card clicked

**Expected outcome**: Correct detail page opens when a card is clicked.  
**Success criteria**: URL changes, detail page loads, heading matches clicked card.  
**Failure conditions**: Wrong page opens, error page, no navigation occurs.

---

## Test Scenario 8: Navigate Between Listing Pages

**Title**: User can navigate between Haso and Hitas listing pages  
**Starting state**: `http://localhost:18080/fi` is loaded

### Steps

1. Navigate to `http://localhost:18080/fi`
2. Navigate to the Haso listing page
3. Verify the Haso listing loads
4. Navigate back using browser back button or a navigation link
5. Navigate to the Hitas listing page
6. Verify the Hitas listing loads
7. Verify navigating between the two pages does not produce errors

**Expected outcome**: Both apartment type listings are independently accessible.  
**Success criteria**: Both listing pages load cleanly in the same session.  
**Failure conditions**: Second navigation fails, session state causes error.

---

## Test Scenario 9: No Apartment Data Shows an Empty State

**Title**: Listing page shows a meaningful empty state if no apartments are available  
**Starting state**: A listing page for a type with no apartments (or filters applied that match nothing)

### Steps

1. Navigate to an apartment listing page
2. If possible, apply a filter that would return zero results (price range with no matches, etc.)
3. Verify the page does not show a server error or blank white screen
4. Verify there is a message indicating no apartments are available  
   (Finnish: "ei tuloksia", "ei asuntoja", or similar)
5. Verify the page navigation and header are still intact

**Expected outcome**: Empty result set is handled with a user-friendly message.  
**Success criteria**: Empty state message present, no error, navigation intact.  
**Failure conditions**: Blank page on empty results, server error, layout broken.

---

## Test Scenario 10: Apartment Listing Breadcrumb Navigation

**Title**: Breadcrumb on detail page links back to listing  
**Starting state**: An apartment detail page is open

### Steps

1. Navigate to any apartment detail page (Haso or Hitas)
2. Locate a breadcrumb element near the top of the content area
3. Verify the breadcrumb shows at least two levels (e.g. "Home > Apartments > Project Name")
4. Click the parent breadcrumb link (e.g. "Asunnot" or the listing page link)
5. Verify navigation returns to the listing page
6. Verify the listing page loads correctly

**Expected outcome**: Breadcrumb navigation returns the user to the correct listing.  
**Success criteria**: Breadcrumb present, clicking parent returns to listing, no error.  
**Failure conditions**: No breadcrumb found, breadcrumb link returns 404.
