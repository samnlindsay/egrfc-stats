# Container Sizing Solutions for Vega-Embed Charts

## Problem
When embedding Vega-Lite charts using `vegaEmbed()`, the container HTML div can become larger than the rendered SVG chart, creating excess whitespace. This occurs because:

1. Vega-Embed automatically wraps the SVG in a `div.vega-embed` container
2. The wrapper's size is determined by the Vega spec's width/height properties + padding/margins
3. Inline container styles alone cannot override the wrapper's sizing

## Solution: CSS Targeting `.vega-embed` Wrapper

Add CSS rule to target the `.vega-embed` class that Vega-Embed automatically creates:

```css
/* In main stylesheet or inline <style> block */
.vega-embed {
    width: fit-content !important;
    height: fit-content !important;
}
```

### Implementation in index.html

Add this CSS to the `<style>` section in the document head:

```html
<style>
    /* ... existing styles ... */
    
    /* Vega-Embed wrapper sizing - collapse to exact chart dimensions */
    .vega-embed {
        width: fit-content !important;
        height: fit-content !important;
    }
</style>
```

### Why This Works

- `fit-content` on `.vega-embed` forces the wrapper to size to its SVG child's natural dimensions
- `!important` ensures it overrides any inline styles or Vega-Embed defaults
- No need to modify container divs or Vega specs
- Works for all charts on the page that use `vegaEmbed()`

### Example Usage

```javascript
// Container div can have flex/layout styles
<div id="squadSizeTrendChart" style="flex: 0 0 auto; ..."></div>

// vegaEmbed() call remains unchanged
vegaEmbed('#squadSizeTrendChart', spec, { actions: false, renderer: 'svg' });

// Result: Container collapses to exact chart width
```

### Tested On
- Results charts (league table pages)
- Squad trend charts (main index.html)
- All Altair-generated standalone HTML files

### Notes
- This solution applies globally to all `.vega-embed` elements
- If selective sizing is needed, use more specific CSS selectors
- Compatible with Bootstrap and other CSS frameworks
- No performance impact
