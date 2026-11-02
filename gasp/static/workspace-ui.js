'use strict';
// Update a live workspace without replacing controls that a person is using.
const GaspWorkspace = (() => {
  function key(node) {
    if (node.nodeType !== 1) return '';
    return node.id || node.dataset.uiKey || (node.dataset.learn
      ? [node.dataset.learn, node.dataset.id || '', node.dataset.sid || ''].join(':')
      : node.tagName === 'DETAILS' ? node.querySelector('summary')?.textContent : '') || '';
  }
  function matches(a, b) {
    return a.nodeType === b.nodeType && a.nodeName === b.nodeName && key(a) === key(b);
  }
  function patch(parent, next) {
    const previous = [...parent.childNodes], used = new Set();
    let cursor = parent.firstChild;
    for (const incoming of [...next.childNodes]) {
      const existing = cursor && !used.has(cursor) && matches(cursor, incoming) ? cursor
        : previous.find(node => !used.has(node) && matches(node, incoming));
      if (!existing) {
        parent.insertBefore(incoming.cloneNode(true), cursor);
        continue;
      }
      used.add(existing);
      if (existing !== cursor) parent.insertBefore(existing, cursor);
      if (existing.nodeType === 1) {
        const retain = name => existing.tagName === 'DETAILS' && name === 'open';
        for (const attr of [...existing.attributes]) {
          if (!retain(attr.name) && !incoming.hasAttribute(attr.name)) existing.removeAttribute(attr.name);
        }
        for (const attr of [...incoming.attributes]) {
          if (!retain(attr.name) && existing.getAttribute(attr.name) !== attr.value) existing.setAttribute(attr.name, attr.value);
        }
        // File selections and focused input values belong to the person until submitted.
        if (existing !== document.activeElement && existing.tagName === 'INPUT' && existing.type !== 'file') {
          existing.value = incoming.value;
          existing.checked = incoming.checked;
        }
        if (!incoming.hasAttribute('data-preserve-children')) patch(existing, incoming);
      } else if (existing.nodeValue !== incoming.nodeValue) existing.nodeValue = incoming.nodeValue;
      cursor = existing.nextSibling;
    }
    for (const node of previous) if (!used.has(node)) node.remove();
  }
  function render(root, html, identity) {
    const template = document.createElement('template');
    template.innerHTML = html;
    if (root.dataset.workspace === identity) patch(root, template.content);
    else { root.replaceChildren(template.content); root.dataset.workspace = identity; }
  }
  return {render};
})();
