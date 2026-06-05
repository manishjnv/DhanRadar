# Page Structure

Each page: server component fetches → dehydrate → <HydrationBoundary> → client useQuery (warm). Public pages ISR. generateMetadata for SEO. Loading via loading.tsx + Suspense; errors via error.tsx boundaries. See /screens/*.md for per-page layout, API, states.
