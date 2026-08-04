// `plotly.js-dist-min` ships no types of its own -- it has the exact same runtime API as `plotly.js`
// (just pre-bundled/minified with all trace types included), so re-export `@types/plotly.js`'s types for
// it here rather than pulling in the full (much larger) `plotly.js` package just for type declarations.
declare module 'plotly.js-dist-min' {
  import * as Plotly from 'plotly.js';
  export = Plotly;
}
