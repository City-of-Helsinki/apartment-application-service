# Drupal Smoke Test Plan

## Application Overview

Smoke test plan for the City of Helsinki apartment application service (asuntotuotanto) Drupal front-end at http://localhost:18080. The site is primarily in Finnish (/fi) with a Swedish variant (/sv). It allows citizens to browse, search, and apply for right-of-occupancy (Haso), price-regulated ownership (Hitas), and half-Hitas apartments. Apartment data is fetched in real time from a Django REST API backend at http://localhost:18081. The stack depends on MariaDB (Drupal DB), PostgreSQL (Django DB), and Elasticsearch (search). Authentication is handled via Helsinki profile / OIDC SSO as well as a local Drupal admin login at /fi/user/login.

## Test Scenarios

### 1. Basic Site Health

**Seed:** `seed.spec.ts`

#### 1.1. Front page loads in Finnish without errors

**File:** `tests/basic-health/front-page.spec.ts`

**Steps:**
  1. Navigate to http://localhost:18080/fi with a clean browser context (no cookies, no cache)
    - expect: HTTP 200 response is received
    - expect: The page title or <h1> contains 'Helsinki' or 'Asuntotuotanto'
    - expect: The page <html> element has lang="fi" or lang="fi-fi"
  2. Inspect the visible page body
    - expect: The body element is not empty
    - expect: No raw PHP stack trace or 'Drupal\...' exception text is visible
    - expect: No '403 Forbidden', '404 Not Found', or '500 Internal Server Error' text is visible
  3. Open the browser developer console and check for error-level messages
    - expect: Zero console errors are present
    - expect: No unhandled JavaScript promise rejections appear

#### 1.2. Static assets are served from the correct host

**File:** `tests/basic-health/static-assets.spec.ts`

**Steps:**
  1. Navigate to http://localhost:18080/fi and monitor all outgoing network requests until page load completes
    - expect: All CSS file requests return HTTP 200
    - expect: All JavaScript file requests return HTTP 200
    - expect: No request URL contains the internal hostname 'drupal-app'
  2. Inspect image requests in the network log
    - expect: All image requests return HTTP 200 or 304
    - expect: No broken image icons (alt text rendered in place of the image) are visible on the page
  3. Check for mixed-content browser warnings
    - expect: No mixed-content warnings appear in the browser console (all assets are served over the same protocol)

#### 1.3. 404 page is rendered with site chrome

**File:** `tests/basic-health/404-handling.spec.ts`

**Steps:**
  1. Navigate to http://localhost:18080/fi/this-page-does-not-exist-abc123xyz
    - expect: The browser receives an HTTP 404 response
    - expect: The response body contains styled HTML rather than a blank page or raw server output
  2. Inspect the rendered 404 page
    - expect: The site header and main navigation are still visible
    - expect: A link back to the front page (Home / Etusivu) is present
    - expect: No PHP error or Drupal exception text is visible

#### 1.4. Kubernetes health probes on the Django backend return 200

**File:** `tests/basic-health/backend-probes.spec.ts`

**Steps:**
  1. Send a GET request to http://localhost:18081/healthz
    - expect: HTTP 200 response is received
  2. Send a GET request to http://localhost:18081/readiness
    - expect: HTTP 200 response is received

### 2. Navigation

**Seed:** `seed.spec.ts`

#### 2.1. Main navigation is present and all links are reachable

**File:** `tests/navigation/main-nav.spec.ts`

**Steps:**
  1. Navigate to http://localhost:18080/fi
    - expect: A primary navigation element (role='navigation' or <nav>) is visible
  2. Enumerate all top-level navigation links
    - expect: At least one navigation link is visible and has a non-empty href attribute
  3. Click each top-level navigation link in turn, then navigate back
    - expect: Each destination page returns HTTP 200
    - expect: No destination page shows a 404 or 500 error banner
    - expect: The browser URL changes to the link's target path after each click

#### 2.2. Language switcher switches site to Swedish

**File:** `tests/navigation/language-switcher.spec.ts`

**Steps:**
  1. Navigate to http://localhost:18080/fi
    - expect: A language switcher control containing 'SV', 'Svenska', or 'EN' is visible on the page
  2. Click the 'SV' or 'Svenska' link in the language switcher
    - expect: The URL changes to /sv/...
    - expect: The page <html lang> attribute changes to 'sv' or 'sv-fi'
    - expect: Visible page content switches to Swedish (at minimum the navigation text changes)
  3. Click the Finnish language link to return
    - expect: The URL changes back to /fi/...
    - expect: Visible content returns to Finnish

#### 2.3. Breadcrumb navigation is present on inner pages

**File:** `tests/navigation/breadcrumbs.spec.ts`

**Steps:**
  1. Navigate to any non-front-page URL (e.g. an apartment listing page)
    - expect: A breadcrumb element is visible near the top of the content area
  2. Inspect the breadcrumb trail
    - expect: At least two breadcrumb items are present (e.g. 'Home' and the current page title)
    - expect: Each breadcrumb item is either a link or plain text
  3. Click the first (home) breadcrumb link
    - expect: Navigation returns to http://localhost:18080/fi
    - expect: The front page loads without error

#### 2.4. Footer is present with content and working links

**File:** `tests/navigation/footer.spec.ts`

**Steps:**
  1. Navigate to http://localhost:18080/fi and scroll to the bottom of the page
    - expect: A <footer> element or element with role='contentinfo' is visible
  2. Inspect footer content
    - expect: At least one link is present in the footer
    - expect: No broken image icons are visible in the footer
    - expect: Footer text is in Finnish
  3. Click one footer link
    - expect: The destination page loads without error

### 3. Haso Apartment Browsing

**Seed:** `seed.spec.ts`

#### 3.1. Haso listing page is accessible from the main navigation

**File:** `tests/haso/listing-page.spec.ts`

**Steps:**
  1. Navigate to http://localhost:18080/fi
    - expect: A navigation link related to right-of-occupancy apartments ('asumisoikeus', 'Haso', or similar) is visible
  2. Click the Haso navigation link
    - expect: The URL navigates to a Haso listing path (e.g. /fi/asumisoikeusasunnot)
    - expect: HTTP 200 is received
    - expect: The page heading contains 'asumisoikeus' or 'Haso'

#### 3.2. Haso listing page displays apartment project cards

**File:** `tests/haso/listing-cards.spec.ts`

**Steps:**
  1. Navigate to the Haso apartment listing page
  2. Count the number of visible apartment project cards or list items
    - expect: At least one apartment project card is visible (assumes fixture data includes Haso projects)
  3. Inspect each visible card
    - expect: Each card contains a project name or title
    - expect: Each card contains a neighbourhood or district name
    - expect: Cards are not visually overlapping or broken

#### 3.3. Haso apartment detail page opens from a listing card

**File:** `tests/haso/detail-page.spec.ts`

**Steps:**
  1. Navigate to the Haso listing page and record the name of the first visible project card
    - expect: At least one card is visible
  2. Click the first project card or its primary link ('Lue lisää' / 'Read more')
    - expect: The URL changes to a project-specific path
    - expect: HTTP 200 is received
    - expect: The page heading matches the project name recorded from the listing card
  3. Inspect the detail page for apartment-specific information
    - expect: At least one of the following is present: address, apartment sizes, price information, or application period
    - expect: The site header and navigation are still visible
    - expect: No broken image placeholders are visible

#### 3.4. Haso listing shows a meaningful empty state when no apartments exist

**File:** `tests/haso/empty-state.spec.ts`

**Steps:**
  1. Navigate to the Haso listing page and apply a filter combination that is expected to return zero results (e.g. an extreme price range or room count)
  2. Observe the filtered result area
    - expect: No server error or blank white screen is shown
    - expect: A Finnish-language empty state message is present (e.g. 'ei tuloksia', 'ei asuntoja', or similar)
    - expect: The site header and navigation remain intact

### 4. Hitas and Puolihitas Apartment Browsing

**Seed:** `seed.spec.ts`

#### 4.1. Hitas listing page is accessible from the main navigation

**File:** `tests/hitas/listing-page.spec.ts`

**Steps:**
  1. Navigate to http://localhost:18080/fi
    - expect: A navigation link related to ownership apartments ('omistusasunnot', 'Hitas', or similar) is visible
  2. Click the Hitas navigation link
    - expect: The URL navigates to a Hitas listing path (e.g. /fi/omistusasunnot)
    - expect: HTTP 200 is received
    - expect: The page heading contains 'omistus' or 'Hitas'

#### 4.2. Hitas listing displays project cards with ownership type label

**File:** `tests/hitas/listing-cards.spec.ts`

**Steps:**
  1. Navigate to the Hitas ownership apartment listing page
  2. Count the visible apartment project cards
    - expect: At least one project card is visible (assumes fixture data includes Hitas projects)
  3. Inspect each card for ownership type indication
    - expect: Each card contains a project name
    - expect: An ownership type label or badge ('Hitas', 'omistus', or 'Puolihitas') is visible on at least one card

#### 4.3. Hitas apartment detail page opens and shows project information

**File:** `tests/hitas/detail-page.spec.ts`

**Steps:**
  1. Navigate to the Hitas listing page, record the name of the first card, and click on it
    - expect: The URL changes to a project-specific path
    - expect: HTTP 200 is received
    - expect: The page heading matches the project name from the listing card
  2. Check detail page content
    - expect: At least one of the following is present: address, apartment sizes, price range, or application period
    - expect: The site header and navigation are still visible

#### 4.4. User can navigate between Haso and Hitas listings in one session

**File:** `tests/hitas/cross-listing-navigation.spec.ts`

**Steps:**
  1. Navigate to the Haso listing page
    - expect: Haso listing loads with HTTP 200
  2. Use the main navigation or browser back to return to the front page, then navigate to the Hitas listing page
    - expect: Hitas listing loads with HTTP 200
    - expect: No session error or stale-state error occurs between the two navigations

### 5. Search and Filtering

**Seed:** `seed.spec.ts`

#### 5.1. Search form is present on the site

**File:** `tests/search/search-form.spec.ts`

**Steps:**
  1. Navigate to http://localhost:18080/fi and look for a search input field (role='searchbox' or type='search')
    - expect: A search input element is found on the page or reachable via a search icon/button in the navigation
  2. Enter a search term related to Helsinki neighbourhoods (e.g. 'Kallio') into the search field and submit
    - expect: The URL changes to a search results path (e.g. /fi/search or /fi/haku)
    - expect: HTTP 200 is received
    - expect: The results area contains content or a 'no results' message in Finnish

#### 5.2. Apartment listing can be filtered by ownership type

**File:** `tests/search/ownership-filter.spec.ts`

**Steps:**
  1. Navigate to an apartment listing page that offers ownership-type filter controls
    - expect: Filter controls (checkboxes, buttons, or a dropdown) for ownership type are visible
  2. Select only 'Hitas' in the ownership type filter
    - expect: The listing updates (either via page reload or in-page filtering)
    - expect: Only Hitas-labelled cards are visible after filtering
    - expect: No Haso-labelled cards remain visible
  3. Clear the filter and select only 'Haso'
    - expect: Only Haso-labelled cards are visible
    - expect: No Hitas-labelled cards remain visible

#### 5.3. Search for a non-existent term returns a friendly empty state

**File:** `tests/search/empty-search.spec.ts`

**Steps:**
  1. Navigate to the site search and enter a term that will return no results (e.g. 'zzzzznotaplacexxx')
  2. Submit the search
    - expect: The page does not return a 500 error
    - expect: A Finnish-language message indicating zero results is shown (e.g. 'Haulla ei löytynyt tuloksia')
    - expect: The site navigation and header remain intact

### 6. User Authentication

**Seed:** `seed.spec.ts`

#### 6.1. Drupal admin login page renders correctly

**File:** `tests/auth/admin-login.spec.ts`

**Steps:**
  1. Navigate to http://localhost:18080/fi/user/login with a fresh browser context
    - expect: HTTP 200 is received
    - expect: A login form is visible containing a username or email field, a password field, and a submit button
  2. Enter invalid credentials (username: 'invalid', password: 'invalid') and submit the form
    - expect: The form submission completes without a 500 error
    - expect: An error message is shown indicating the credentials are wrong (Finnish: 'virheellinen käyttäjätunnus tai salasana' or similar)
    - expect: The login form is still displayed after the failed attempt

#### 6.2. Helsinki profile SSO login entry point is present for citizens

**File:** `tests/auth/sso-link.spec.ts`

**Steps:**
  1. Navigate to http://localhost:18080/fi and look for a 'Kirjaudu sisään' (log in) button or link in the header or navigation
    - expect: A login button or link is visible to anonymous users
  2. Click the login button
    - expect: The user is directed to a Helsinki profile / OIDC login page or the Drupal login page
    - expect: HTTP 200 is received at the destination
    - expect: No server error is shown

#### 6.3. Authenticated user session persists across page navigations

**File:** `tests/auth/session-persistence.spec.ts`

**Steps:**
  1. Log in to Drupal admin at /fi/user/login with valid admin credentials
    - expect: Login succeeds without a 500 error
    - expect: The user is redirected to /fi/user/<uid> or /admin or similar post-login page
    - expect: A logout link ('Kirjaudu ulos' or 'Log out') is visible in the navigation
  2. Navigate to http://localhost:18080/fi (front page)
    - expect: The logout link is still visible, confirming the session persists
    - expect: No login form re-appears
  3. Navigate to http://localhost:18080/fi/user/logout
    - expect: The user is logged out
    - expect: A login link or button re-appears in the navigation
    - expect: The session cookie is cleared (no 'already logged in' message on revisiting the login page)

#### 6.4. Accessing a restricted page as an anonymous user redirects to login

**File:** `tests/auth/anonymous-redirect.spec.ts`

**Steps:**
  1. As an unauthenticated user, navigate to http://localhost:18080/admin
    - expect: The user is redirected to the login page or receives an HTTP 403 response
    - expect: No Drupal admin dashboard content is visible to the anonymous user

### 7. Apartment Application Flow

**Seed:** `seed.spec.ts`

#### 7.1. Apply button is visible on a Haso or Hitas project detail page

**File:** `tests/application/apply-button.spec.ts`

**Steps:**
  1. Navigate to an apartment project detail page that has an open application period
  2. Locate a call-to-action for applying ('Hae asuntoa', 'Jätä hakemus', 'Apply', or similar)
    - expect: An apply button or link is visible on the detail page
    - expect: The button is not disabled when the application period is open

#### 7.2. Unauthenticated user attempting to apply is prompted to log in

**File:** `tests/application/unauthenticated-apply.spec.ts`

**Steps:**
  1. As an unauthenticated user, navigate to an apartment project detail page with an open application period and click the apply button
    - expect: The user is redirected to the login page or shown a login prompt
    - expect: No application form content is shown to an anonymous user
    - expect: No server error occurs

#### 7.3. Application form is displayed to an authenticated citizen

**File:** `tests/application/application-form.spec.ts`

**Steps:**
  1. Log in as an authenticated citizen using Helsinki profile SSO or a test account
    - expect: Authentication succeeds
  2. Navigate to an apartment project detail page with an open application period and click the apply button
    - expect: An application form is rendered
    - expect: Required fields are labelled clearly in Finnish
    - expect: The form contains at minimum: applicant personal details, apartment preference selection, and a submit button
  3. Submit the form without filling any required fields
    - expect: Validation errors are shown for all required fields in Finnish
    - expect: The form is not submitted and no HTTP POST is made to the backend
    - expect: No server error is returned

#### 7.4. Application form validates required fields before submission

**File:** `tests/application/form-validation.spec.ts`

**Steps:**
  1. Open an apartment application form as an authenticated user
  2. Fill in all required fields with valid data and submit the form
    - expect: The form is accepted and submitted successfully
    - expect: A confirmation message or redirect to a 'success' page is shown in Finnish
    - expect: No HTTP 4xx or 5xx error is returned
  3. Attempt to re-submit the same application for the same apartment
    - expect: An appropriate error message is shown (e.g. 'Olet jo hakenut tätä asuntoa')
    - expect: No duplicate application is created

### 8. Django API Integration

**Seed:** `seed.spec.ts`

#### 8.1. Django REST API is reachable from the host and returns apartment data

**File:** `tests/api-integration/django-api.spec.ts`

**Steps:**
  1. Send a GET request to http://localhost:18081/v1/sales/projects/ with an appropriate authentication header
    - expect: HTTP 200 or HTTP 401 (if auth required) is returned
    - expect: The response body is valid JSON
    - expect: No HTTP 5xx error is returned
  2. Send a GET request to http://localhost:18081/v1/sales/apartments/
    - expect: HTTP 200 or HTTP 401 is returned
    - expect: The response Content-Type header indicates JSON

#### 8.2. Drupal listing pages reflect apartment data served by Django

**File:** `tests/api-integration/drupal-django-sync.spec.ts`

**Steps:**
  1. Navigate to the Haso apartment listing page on Drupal
    - expect: The page loads with HTTP 200
  2. Note the names of the apartment projects shown
    - expect: At least one project name visible in the Drupal listing also exists as a project in the Django API response from /v1/sales/projects/ (confirming data flows from Django to Drupal)

#### 8.3. API documentation endpoint is accessible

**File:** `tests/api-integration/api-docs.spec.ts`

**Steps:**
  1. Navigate to http://localhost:18081/api_docs/
    - expect: HTTP 200 is received
    - expect: An API documentation page (Redoc) renders without error
  2. Navigate to http://localhost:18081/api_docs/swagger/
    - expect: HTTP 200 is received
    - expect: A Swagger UI page renders without error
