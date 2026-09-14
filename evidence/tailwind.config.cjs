// Merged in as a Tailwind preset by the Evidence template, which looks for a
// tailwind.config.{js,cjs} two levels above .evidence/template -- that is, here.
//
// Evidence's own preset sets sans to Inter and serif to Spectral. The website is set in
// Poppins with JetBrains Mono for code, so both are replaced. The faces themselves are
// declared in app.css and served from static/fonts.
/** @type {import("tailwindcss").Config} */
module.exports = {
	theme: {
		extend: {
			fontFamily: {
				sans: ['Poppins', 'Helvetica Neue', 'Arial', 'sans-serif'],
				mono: ['JetBrains Mono', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace']
			}
		}
	}
};
