<script>
	// Overrides the Evidence template's own +layout.svelte: the CLI copies pages/ into the
	// template's src/pages/, so this file wins. It exists to put the JB Analytica wordmark in
	// the header in place of Evidence's, and to point the repo link at this project.
	//
	// The template imports @evidence-dev/tailwind/fonts.css here for Inter and Spectral. That
	// import is deliberately absent: Poppins and JetBrains Mono are declared in app.css, and
	// loading two more families on a public site for nothing is waste.
	import '../app.css';
	import { EvidenceDefaultLayout } from '@evidence-dev/core-components';
	export let data;
</script>

<EvidenceDefaultLayout
	{data}
	logo="/jba-logo.png"
	githubRepo="https://github.com/JB-Analytica/reference-architecture"
>
	<slot slot="content" />
</EvidenceDefaultLayout>
