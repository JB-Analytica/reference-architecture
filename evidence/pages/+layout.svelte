<script>
	// Overrides the Evidence template's own +layout.svelte: the CLI copies pages/ into the
	// template's src/pages/, so this file wins. It exists to put the JB Analytica wordmark in
	// the header in place of Evidence's, to point the repo link at this project, and to wrap
	// every page in the provenance line and footer below.
	//
	// The template imports @evidence-dev/tailwind/fonts.css here for Inter and Spectral. That
	// import is deliberately absent: Poppins and JetBrains Mono are declared in app.css, and
	// loading two more families on a public site for nothing is waste.
	import '../app.css';
	import { base } from '$app/paths';
	import { EvidenceDefaultLayout } from '@evidence-dev/core-components';
	export let data;

	const SITE = 'https://www.jbanalytica.com';
	const REPO = 'https://github.com/JB-Analytica/reference-architecture';
</script>

<EvidenceDefaultLayout
	{data}
	logo="{base}/jba-logo.png"
	githubRepo={REPO}
>
	<div slot="content">
		<!-- Above the fold on every page, not just the home page. Someone who arrives on
		     /cancellations from a shared link has to be able to tell whose site this is and
		     that nothing on it is real, without scrolling or navigating. -->
		<p class="text-xs text-base-content-muted mb-4">
			<a href={SITE} class="underline hover:text-base-content">JB Analytica</a>
			reference architecture — a published example. The business and every figure on it are
			invented.
		</p>

		<slot />

		<footer class="mt-12 pt-6 border-t border-base-300 text-xs text-base-content-muted">
			<p class="mb-3">
				This is a reference project by
				<a href={SITE} class="underline hover:text-base-content">JB Analytica</a>, a data
				architecture and analytics engineering consultancy in Belgium. It is not a client
				engagement: the coffee webshop does not exist, and the customers, orders and revenue
				shown here are generated data. Every line of it is published.
			</p>
			<p class="flex flex-wrap gap-x-4 gap-y-1">
				<a href={SITE} class="underline hover:text-base-content">jbanalytica.com</a>
				<a href="{SITE}/#contact" class="underline hover:text-base-content">
					Book a scoping call
				</a>
				<a href={REPO} class="underline hover:text-base-content">
					Source on GitHub
				</a>
			</p>
		</footer>
	</div>
</EvidenceDefaultLayout>
