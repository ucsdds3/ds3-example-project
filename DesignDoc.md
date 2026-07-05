# PlantDex Design Document

## Overview

PlantDex is a full-stack plant discovery platform that helps users search for familiar plants and explore related species, lesser-known relatives, and similar plants. The project belongs to the intersection of web development, API integration, data organization, and lightweight recommendation systems.

Instead of only identifying a plant, PlantDex helps users understand a plant’s broader botanical context. For example, a user searching “blueberry” could discover related species such as bilberries, lingonberries, cranberries, and other plants in the *Vaccinium* genus or Ericaceae family.

This is not primarily a machine learning project in its first version. The MVP focuses on external API integration, taxonomy-based recommendations, user collections, and cloud deployment. Later versions may include AI-generated explanations, personalized recommendations, or location-based growing advice.

## Customer Identification & Problem Statement

The target users are gardeners, students, plant hobbyists, educators, and curious users who want to learn more about plants beyond a single common name. Many people know broad plant names like “blueberry,” “maple,” or “monstera,” but they may not realize that each name can refer to many species, cultivars, or related plants. This problem is even more apparent when working with rare species native to non-English speaking countries, as translated names often coincide with related, but not identical, species (eg. custard apple - annona reticulata & sugar apple - annona squamosa).

The main pain point is that existing plant tools often focus on identification, care reminders, or plant shopping. They usually do not make it easy to explore botanical relationships in an accessible way. A user may want to know: What species are related to this plant? Are there lesser-known edible relatives? What plants are in the same genus or family? How do similar plants compare?

This problem matters because plant literacy is useful for gardening, ecology, agriculture, biodiversity awareness, and education. A successful outcome would be a deployed website where users can search a plant, view plant profiles, discover related plants, compare them, and save them into personal collections.

## Background Research and Related Work

Existing plant applications often focus on plant identification from images, care tracking, or marketplace-style plant browsing. Examples include plant identification apps, gardening apps, nursery websites, and plant databases.

PlantDex differs by focusing on botanical discovery rather than diagnosis or care scheduling. It uses the Trefle API as a plant metadata source, especially for common names, scientific names, taxonomy, images, and basic plant traits. The recommendation system will initially be rule-based rather than ML-based, using features such as shared genus, shared family, edible or vegetable flags, growth habit, and similar common-name tokens.

Related tools and concepts include:

- Trefle API for plant taxonomy and metadata
- USDA PLANTS Database for plant distribution and standardized plant records
- GBIF and iNaturalist-style biodiversity databases
- Plant identification apps such as PictureThis or PlantNet
- Recommendation systems based on similarity scoring and metadata matching
- Collection-based apps such as Beli, Letterboxd, or Pinterest

## Goals

The main goals of PlantDex are:

1. Allow users to search for plants by common or scientific name.
2. Display plant results as clean image cards with names and key metadata.
3. Provide detailed plant profile pages with common name, scientific name, genus, family, image, distribution, edible status, and growth traits when available.
4. Recommend similar or related plants using taxonomy and metadata-based similarity.
5. Let users compare 2-4 plants side by side.
6. Allow authenticated users to create and manage plant collections.
7. Deploy the application on Google Cloud, likely using Cloud Run, Firestore, Firebase Auth, and Secret Manager.
8. Cache Trefle API responses to reduce repeated external API calls and improve performance.

## Non-Goals

The first version of PlantDex will not attempt to:

1. Provide guaranteed local growing recommendations by ZIP code.
2. Recommend specific cultivars for a user’s climate.
3. Diagnose plant diseases from images.
4. Use computer vision for plant identification.
5. Provide professional agricultural or horticultural advice.
6. Support marketplace purchases or nursery inventory.
7. Train a custom machine learning model.
8. Fully verify all Trefle data manually.

These may be considered future extensions once the core discovery platform is stable.

## System Architecture

```mermaid

```

The frontend handles search, profile display, comparison views, and user collections. The backend communicates with the Trefle API, normalizes plant data, computes similarity rankings, and stores cached plant data in Firestore. Firebase Auth manages user login, while Secret Manager stores the Trefle API key securely.

## Data Sources

The primary data source is the Trefle API. Trefle provides plant information such as common names, scientific names, taxonomy, images, distribution, and selected growth traits. The data is public and accessed through an external REST API.

The project will store selected API responses in Firestore to improve performance and reduce redundant API calls. Cached records may include:

```text
cachedPlants/{treflePlantId}
- common_name
- scientific_name
- genus
- family
- image_url
- edible
- vegetable
- distribution
- growth_form
- raw_trefle_response
- cached_at
```

User-generated data will also be stored in Firestore:

```text
users/{userId}
collections/{collectionId}
collections/{collectionId}/plants/{plantId}
```

Known data issues include missing images, incomplete traits, inconsistent common names, and limited cultivar-level data. These issues will be handled through fallback UI states, null-safe parsing, and clear labels when data is unavailable.

API credentials will not be committed to GitHub. The Trefle API key will be stored in Google Cloud Secret Manager for deployment and referenced through environment configuration.

## Execution Flow

1. A user visits the PlantDex website.
2. The user searches for a plant, such as “blueberry.”
3. The frontend sends the query to the backend API.
4. The backend checks Firestore for cached search results.
5. If no fresh cache exists, the backend calls the Trefle API.
6. The backend normalizes the Trefle response into a consistent plant result format.
7. The frontend displays matching plants as image cards.
8. The user selects a plant to open its profile page.
9. The backend fetches or retrieves cached detailed plant data.
10. The profile page displays taxonomy, image, traits, distribution, and metadata.
11. The backend computes related plants using genus, family, edible status, growth habit, and name similarity.
12. The user can compare related plants or save them to a personal collection.
13. Authenticated users can create, update, and delete collections.

## Security and Configuration

The project will use environment variables and cloud-managed secrets for configuration. Local development may use a `.env` file, but actual secrets will not be committed to GitHub. A `.env.example` file can document required variables.

Example:

```env
TREFLE_API_KEY=your_api_key_here
FIREBASE_PROJECT_ID=your_project_id
GOOGLE_CLOUD_PROJECT=your_gcp_project
```

Security practices include:

- Store Trefle API key in Secret Manager for production.
- Use Firebase Auth for user identity.
- Use Firestore security rules to ensure users can only modify their own collections.
- Validate all user inputs on the backend.
- Rate-limit or cache repeated plant searches.
- Avoid exposing raw API keys in frontend code.

Dependencies will be managed through `package.json` for the frontend and either `requirements.txt`/`pyproject.toml` or `package.json` for the backend, depending on whether FastAPI or Node/Express is used.

## Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Trefle data is incomplete or missing fields | Build fallback UI states and store raw responses for debugging |
| Trefle API rate limits or downtime | Cache search results and plant profiles in Firestore |
| Similar plant recommendations feel weak | Start with transparent rule-based scoring and improve over time |
| User searches vague names like “berry” or “tree” | Use autocomplete, ranked results, and clarify common vs scientific names |
| API key exposure | Keep Trefle calls on the backend and store secrets in Secret Manager |
| Scope creep into climate/cultivar recommendations | Keep ZIP-code growing recommendations as a future extension |
| Firestore data model becomes messy | Define clear schemas for cached plants, users, and collections early |
| Deployment complexity | Use Cloud Run and Firebase services to keep infrastructure lightweight |

## Rollout Plan

The project will be developed in stages.

### Phase 1: MVP Search and Profiles

Build the frontend search page, backend Trefle integration, and plant profile pages. Add basic caching in Firestore.

### Phase 2: Related Plant Discovery

Implement related plant recommendations using genus, family, edible status, growth habit, and common-name similarity.

### Phase 3: Collections and Auth

Add Firebase Auth and allow users to save plants into custom collections such as “Plants I own,” “Backyard fruit ideas,” or “Lesser-known berries.”

### Phase 4: Compare Plants

Build a comparison page where users can select 2-4 plants and compare taxonomy, images, growth traits, edible status, and distribution.

### Phase 5: Cloud Deployment and Testing

Deploy the backend to Cloud Run, connect it to Secret Manager and Firestore, and deploy the frontend. Test search, profile loading, auth, collections, and caching.

### Phase 6: Future Extensions

Possible future features include ZIP-code growing suitability, AI-generated explanations, educational plant maps, public collections, and curated plant discovery paths such as “Plants related to common grocery fruits.”