# Draft architecture diagrams with diagrams.net

## When to use
- A network or architecture diagram needs more control than Mermaid provides.
- The deliverable must be editable in diagrams.net and render directly in GitHub.
- A comparison diagram must show trust boundaries, private paths, public paths, and
  service-placement differences.

## Deliverables
Create all three artifacts:

1. `<name>.drawio` - editable, uncompressed diagrams.net XML and the source of truth.
2. `<name>.svg` - a repository-friendly rendering with selectable text.
3. `<name>.md` - a short explanation that embeds the SVG and links to the `.drawio` source.

Do not upload diagrams, repository content, or credentials to a hosted diagram service.

## Visual language
- Use a 16:9 landscape canvas unless the content requires a different aspect ratio.
- Use containers to show on-premises, customer VNet, subnet, and Microsoft-managed
  boundaries.
- Use solid blue arrows for private data-plane traffic.
- Use dashed gray arrows for control-plane or management traffic.
- Use red only for public exposure, blocked paths, or security warnings.
- Keep node labels short. Put implementation detail in the Markdown comparison table.
- Stack architecture alternatives vertically by default so each traffic path gets the full
  canvas width. Use side-by-side panels only when each alternative has four or fewer nodes
  and labels remain readable at repository preview width.
- Add a legend and a one-sentence takeaway inside comparison diagrams.
- Use Azure architecture icons only from Microsoft's official Azure architecture icon set.
  Put the product name next to each icon. Never crop, flip, rotate, recolor, distort, or use
  a Microsoft icon to represent a custom service.

## Microsoft presentation standard
- Follow the Azure Well-Architected
  [Architecture design diagrams](https://learn.microsoft.com/azure/well-architected/architect-role/design-diagrams)
  guidance and the official
  [Azure architecture icon rules](https://learn.microsoft.com/azure/architecture/icons/).
- Prefer a white canvas, Segoe UI, official icons at consistent sizes, thin neutral
  boundaries, and minimal decorative effects.
- Do not use shadows, gradients, or large colored title bands except where they convey a
  documented semantic distinction.
- Use single-ended directional arrows. Show two arrows for genuinely bidirectional flows.
- Include a compact legend for every line, border, or fill convention.
- Include title, purpose, version, last-updated date, and documentation references.
- Ensure adequate contrast and never rely on color alone; pair color with labels, line
  styles, or boundary titles.
- Treat Azure Architecture Center examples as the visual reference, not marketing slides.

## Accuracy rules
- Distinguish resource placement from connectivity. A private endpoint does not place the
  target service inside the VNet.
- Distinguish gateway data-plane isolation from the Azure Resource Manager control plane.
- Label public access as disabled only when the design explicitly configures it.
- Show separate subnets when Azure requires separate delegation or private-endpoint
  placement.
- Never imply that advertised regional SKU availability guarantees physical capacity.

## Workflow
1. Read the infrastructure and current Microsoft documentation for the features shown.
2. Write a short inventory of boundaries, components, and directional flows.
3. Draft the `.drawio` source with explicit geometry; do not rely on automatic layout.
4. Open the source in diagrams.net and check alignment, overlap, font size, and arrow
   direction.
5. Export SVG with:
   `./scripts/export-drawio.ps1 -InputPath <name>.drawio -OutputPath <name>.svg`
6. Inspect the SVG at normal width and at 50 percent zoom.
7. Embed it in Markdown:
   `[![Diagram title](./<name>.svg)](./<name>.drawio)`
8. Validate the XML and repository diff:
   `try { [xml](Get-Content <name>.drawio -Raw) | Out-Null } catch { throw }`
   `git diff --check`

## diagrams.net source requirements
- Save uncompressed XML so diffs remain reviewable.
- Use stable semantic cell IDs such as `premium-apim` instead of generated IDs.
- Keep presentation text in node values and explanatory detail in Markdown.
- Give every edge a source and target rather than relying on loose connectors.
- Keep the editable source and SVG names aligned.
- Regenerate the SVG whenever the `.drawio` source changes.

## Fallback when diagrams.net Desktop is unavailable
Draft and validate the uncompressed `.drawio` source, then create a matching SVG using the
same canvas geometry and labels. State that diagrams.net Desktop is required for a canonical
re-export. Do not install software or use an online converter without user approval.
