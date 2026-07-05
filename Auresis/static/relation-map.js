(function () {
    var root = document.querySelector('[data-relation-map]');
    if (!root) return;

    var svg = root.querySelector('svg');
    var loading = root.querySelector('.relation-map__loading');
    var detail = document.querySelector('[data-map-detail]');
    var nodeFilters = Array.prototype.slice.call(document.querySelectorAll('[data-map-filter]'));
    var linkFilters = Array.prototype.slice.call(document.querySelectorAll('[data-link-filter]'));
    var resetButton = document.querySelector('[data-map-reset]');
    var focusButton = document.querySelector('[data-map-focus]');
    var searchInput = document.querySelector('[data-map-search]');
    var questSelect = document.querySelector('[data-map-quest-filter]');
    var activeNodeFilter = 'all';
    var activeLinkFilter = 'all';
    var selectedNodeId = null;
    var focusMode = false;
    var activeQuestId = 'all';
    var graph = { nodes: [], links: [] };
    var transform = { x: 0, y: 0, scale: 1 };
    var viewport = null;
    var draggingCanvas = null;
    var draggingNode = null;
    var MAX_INITIAL_NODES = 80;

    function kindLabel(kind) {
        return { npc: 'NPC', quest: 'Quest', luogo: 'Luogo', fazione: 'Fazione' }[kind] || kind;
    }

    function normalize(text) {
        return String(text || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
    }

    function visibleNodeByControls(node) {
        var query = normalize(searchInput ? searchInput.value : '');
        var nodeMatch = activeNodeFilter === 'all' || node.kind === activeNodeFilter;
        var searchMatch = !query || normalize(node.label + ' ' + node.subtitle).indexOf(query) !== -1;
        return nodeMatch && searchMatch;
    }

    function questNeighborhoodIds() {
        if (activeQuestId === 'all') return null;
        var ids = new Set([activeQuestId]);
        graph.links.forEach(function (link) {
            if (link.source === activeQuestId) ids.add(link.target);
            if (link.target === activeQuestId) ids.add(link.source);
        });
        return ids;
    }

    function visibleGraph() {
        var questIds = questNeighborhoodIds();
        var baseNodes = graph.nodes.filter(function (node) {
            return visibleNodeByControls(node) && (!questIds || questIds.has(node.id));
        });
        var baseIds = new Set(baseNodes.map(function (node) { return node.id; }));
        var links = graph.links.filter(function (link) {
            return baseIds.has(link.source) && baseIds.has(link.target) && (activeLinkFilter === 'all' || link.kind === activeLinkFilter);
        });

        if (focusMode && selectedNodeId) {
            var focusIds = new Set([selectedNodeId]);
            graph.links.forEach(function (link) {
                if (link.source === selectedNodeId) focusIds.add(link.target);
                if (link.target === selectedNodeId) focusIds.add(link.source);
            });
            baseNodes = baseNodes.filter(function (node) { return focusIds.has(node.id); });
            baseIds = new Set(baseNodes.map(function (node) { return node.id; }));
            links = links.filter(function (link) { return baseIds.has(link.source) && baseIds.has(link.target); });
        } else if (!searchInput?.value && activeNodeFilter === 'all' && baseNodes.length > MAX_INITIAL_NODES) {
            var linkedIds = new Set();
            links.slice(0, MAX_INITIAL_NODES * 2).forEach(function (link) {
                linkedIds.add(link.source);
                linkedIds.add(link.target);
            });
            baseNodes = baseNodes.filter(function (node) { return linkedIds.has(node.id); }).slice(0, MAX_INITIAL_NODES);
            baseIds = new Set(baseNodes.map(function (node) { return node.id; }));
            links = links.filter(function (link) { return baseIds.has(link.source) && baseIds.has(link.target); });
        }

        return { nodes: baseNodes, links: links };
    }

    function seedLayout(nodes, width, height) {
        var ring = Math.min(width, height) * 0.34;
        var centerX = width / 2;
        var centerY = height / 2;
        nodes.forEach(function (node, index) {
            if (typeof node.x === 'number' && typeof node.y === 'number') return;
            var angle = (Math.PI * 2 * index) / Math.max(nodes.length, 1) - Math.PI / 2;
            var kindOffset = { fazione: -0.22, npc: 0.04, quest: 0.18, luogo: 0.36 }[node.kind] || 0;
            node.x = centerX + Math.cos(angle + kindOffset) * ring;
            node.y = centerY + Math.sin(angle + kindOffset) * ring;
        });
    }

    function runForces(nodes, links, width, height) {
        var byId = {};
        nodes.forEach(function (node) { byId[node.id] = node; node.vx = node.vx || 0; node.vy = node.vy || 0; });
        for (var step = 0; step < 110; step += 1) {
            nodes.forEach(function (a, i) {
                for (var j = i + 1; j < nodes.length; j += 1) {
                    var b = nodes[j];
                    var dx = (b.x - a.x) || 0.01;
                    var dy = (b.y - a.y) || 0.01;
                    var dist2 = dx * dx + dy * dy;
                    var force = Math.min(4200 / dist2, 2.6);
                    var dist = Math.sqrt(dist2);
                    var fx = (dx / dist) * force;
                    var fy = (dy / dist) * force;
                    a.vx -= fx; a.vy -= fy;
                    b.vx += fx; b.vy += fy;
                }
            });
            links.forEach(function (link) {
                var source = byId[link.source];
                var target = byId[link.target];
                if (!source || !target) return;
                var dx = target.x - source.x;
                var dy = target.y - source.y;
                var dist = Math.sqrt(dx * dx + dy * dy) || 1;
                var desired = link.kind === 'coinvolge' ? 185 : 150;
                var force = (dist - desired) * 0.014;
                var fx = (dx / dist) * force;
                var fy = (dy / dist) * force;
                source.vx += fx; source.vy += fy;
                target.vx -= fx; target.vy -= fy;
            });
            nodes.forEach(function (node) {
                var cx = width / 2;
                var cy = height / 2;
                node.vx += (cx - node.x) * 0.002;
                node.vy += (cy - node.y) * 0.002;
                node.vx *= 0.82;
                node.vy *= 0.82;
                node.x = clamp(node.x + node.vx, 72, width - 230);
                node.y = clamp(node.y + node.vy, 54, height - 92);
            });
        }
    }

    function clamp(value, min, max) {
        return Math.max(min, Math.min(max, value));
    }

    function ensureViewport(width, height) {
        svg.setAttribute('viewBox', '0 0 ' + width + ' ' + height);
        svg.innerHTML = '';
        viewport = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        viewport.setAttribute('class', 'relation-map__viewport');
        svg.appendChild(viewport);
        applyTransform();
    }

    var tickingTransform = false;
    function applyTransform() {
        if (!viewport) return;
        if (!tickingTransform) {
            window.requestAnimationFrame(function() {
                viewport.setAttribute('transform', 'translate(' + transform.x + ' ' + transform.y + ') scale(' + transform.scale + ')');
                tickingTransform = false;
            });
            tickingTransform = true;
        }
    }

    var tickingRender = false;
    function requestRender() {
        if (!tickingRender) {
            window.requestAnimationFrame(function() {
                render();
                tickingRender = false;
            });
            tickingRender = true;
        }
    }

    function render() {
        var width = Math.max(root.clientWidth, 760);
        var height = Math.max(root.clientHeight, 620);
        ensureViewport(width, height);
        var current = visibleGraph();
        var nodes = current.nodes;
        var links = current.links;
        var byId = {};
        nodes.forEach(function (node) { byId[node.id] = node; });
        seedLayout(nodes, width, height);
        if (!draggingNode) runForces(nodes, links, width, height);
        drawLinks(links, byId);
        drawNodes(nodes, width, height);
        updateSummary(nodes.length, links.length);
    }

    function drawLinks(links, byId) {
        links.forEach(function (link) {
            var source = byId[link.source];
            var target = byId[link.target];
            if (!source || !target) return;
            var line = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            var mid = (source.x + target.x) / 2;
            line.setAttribute('d', 'M ' + source.x + ' ' + source.y + ' C ' + mid + ' ' + source.y + ', ' + mid + ' ' + target.y + ', ' + target.x + ' ' + target.y);
            line.setAttribute('class', 'relation-map__link relation-map__link--' + link.kind);
            viewport.appendChild(line);
        });
    }

    function drawNodes(nodes, width, height) {
        nodes.forEach(function (node) {
            var group = document.createElementNS('http://www.w3.org/2000/svg', 'g');
            group.setAttribute('class', 'relation-map__node relation-map__node--' + node.kind + (node.id === selectedNodeId ? ' is-selected' : ''));
            group.setAttribute('transform', 'translate(' + node.x + ' ' + node.y + ')');
            group.setAttribute('tabindex', '0');
            group.setAttribute('role', 'button');

            var circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
            circle.setAttribute('r', node.kind === 'quest' ? 20 : 17);
            group.appendChild(circle);

            var label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            label.setAttribute('x', 26);
            label.setAttribute('y', -3);
            label.textContent = truncate(node.label, 24);
            group.appendChild(label);

            var meta = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            meta.setAttribute('x', 26);
            meta.setAttribute('y', 13);
            meta.setAttribute('class', 'relation-map__node-meta');
            meta.textContent = kindLabel(node.kind);
            group.appendChild(meta);

            group.addEventListener('pointerdown', function (event) {
                event.preventDefault();
                event.stopPropagation();
                draggingNode = { node: node, pointerId: event.pointerId };
                group.setPointerCapture(event.pointerId);
                selectNode(node, false);
            });
            group.addEventListener('pointermove', function (event) {
                if (!draggingNode || draggingNode.node !== node) return;
                var point = clientToSvg(event.clientX, event.clientY);
                node.x = clamp(point.x, 72, width - 230);
                node.y = clamp(point.y, 54, height - 92);
                requestRender();
            });
            group.addEventListener('pointerup', function () { draggingNode = null; });
            group.addEventListener('click', function () { selectNode(node, true); });
            group.addEventListener('keydown', function (event) {
                if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    selectNode(node, true);
                }
            });
            viewport.appendChild(group);
        });
    }

    function renderDetailHtml(markup) {
        if (!detail) return;
        var slot = detail.querySelector('[data-relation-react-overlay]');
        detail.innerHTML = markup;
        if (slot) detail.appendChild(slot);
    }

    function updateSummary(nodeCount, linkCount) {
        if (!detail || selectedNodeId) return;
        renderDetailHtml('' +
            '<p class="relation-map__detail-eyebrow">Vista corrente</p>' +
            '<h2>' + nodeCount + ' nodi</h2>' +
            '<p>' + linkCount + ' collegamenti visibili. Cerca o seleziona un nodo, poi usa Focus per ridurre la mappa ai legami diretti.</p>');
    }

    function truncate(value, length) {
        value = String(value || '');
        return value.length > length ? value.slice(0, length - 1) + '…' : value;
    }

    function clientToSvg(clientX, clientY) {
        var rect = svg.getBoundingClientRect();
        return {
            x: (clientX - rect.left - transform.x) / transform.scale,
            y: (clientY - rect.top - transform.y) / transform.scale
        };
    }

    function selectNode(node, shouldRender) {
        selectedNodeId = node.id;
        var linked = graph.links.filter(function (link) { return link.source === node.id || link.target === node.id; });
        renderDetailHtml('' +
            '<p class="relation-map__detail-eyebrow">' + kindLabel(node.kind) + '</p>' +
            '<h2>' + escapeHtml(node.label) + '</h2>' +
            '<p>' + escapeHtml(node.subtitle || 'Nessuna nota breve') + '</p>' +
            '<p class="relation-map__detail-count">' + linked.length + ' collegamenti totali</p>' +
            '<button type="button" class="detail-drawer__link relation-map__focus-action" data-focus-selected>Mostra legami diretti</button>' +
            '<a class="detail-drawer__link" href="' + node.url + '">Apri scheda completa</a>');
        var focusAction = detail.querySelector('[data-focus-selected]');
        if (focusAction) focusAction.addEventListener('click', function () {
            focusMode = true;
            if (focusButton) focusButton.classList.add('is-active');
            render();
        });
        if (shouldRender) render();
    }

    function escapeHtml(value) {
        return String(value || '').replace(/[&<>'"]/g, function (char) {
            return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' })[char];
        });
    }

    svg.addEventListener('pointerdown', function (event) {
        if (event.target.closest && event.target.closest('.relation-map__node')) return;
        draggingCanvas = { x: event.clientX, y: event.clientY, tx: transform.x, ty: transform.y, pointerId: event.pointerId };
        svg.setPointerCapture(event.pointerId);
    });
    svg.addEventListener('pointermove', function (event) {
        if (!draggingCanvas) return;
        transform.x = draggingCanvas.tx + (event.clientX - draggingCanvas.x);
        transform.y = draggingCanvas.ty + (event.clientY - draggingCanvas.y);
        applyTransform();
    });
    svg.addEventListener('pointerup', function () { draggingCanvas = null; });
    svg.addEventListener('wheel', function (event) {
        event.preventDefault();
        var rect = svg.getBoundingClientRect();
        var mouseX = event.clientX - rect.left;
        var mouseY = event.clientY - rect.top;
        var oldScale = transform.scale;
        var nextScale = clamp(oldScale * (event.deltaY < 0 ? 1.12 : 0.88), 0.45, 2.4);
        transform.x = mouseX - ((mouseX - transform.x) / oldScale) * nextScale;
        transform.y = mouseY - ((mouseY - transform.y) / oldScale) * nextScale;
        transform.scale = nextScale;
        applyTransform();
    }, { passive: false });

    nodeFilters.forEach(function (button) {
        button.addEventListener('click', function () {
            activeNodeFilter = button.dataset.mapFilter || 'all';
            nodeFilters.forEach(function (b) { b.classList.toggle('is-active', b === button); });
            selectedNodeId = null;
            render();
        });
    });
    linkFilters.forEach(function (button) {
        button.addEventListener('click', function () {
            activeLinkFilter = button.dataset.linkFilter || 'all';
            linkFilters.forEach(function (b) { b.classList.toggle('is-active', b === button); });
            render();
        });
    });
    if (searchInput) searchInput.addEventListener('input', function () { selectedNodeId = null; render(); });
    if (questSelect) questSelect.addEventListener('change', function () {
        activeQuestId = questSelect.value || 'all';
        selectedNodeId = activeQuestId === 'all' ? null : activeQuestId;
        focusMode = false;
        if (focusButton) focusButton.classList.remove('is-active');
        render();
        var selected = graph.nodes.find(function (node) { return node.id === activeQuestId; });
        if (selected) selectNode(selected, false);
    });
    if (focusButton) focusButton.addEventListener('click', function () {
        focusMode = !focusMode;
        focusButton.classList.toggle('is-active', focusMode);
        render();
    });
    if (resetButton) resetButton.addEventListener('click', function () {
        transform = { x: 0, y: 0, scale: 1 };
        selectedNodeId = null;
        focusMode = false;
        if (focusButton) focusButton.classList.remove('is-active');
        if (searchInput) searchInput.value = '';
        if (questSelect) questSelect.value = 'all';
        activeQuestId = 'all';
        activeNodeFilter = 'all';
        activeLinkFilter = 'all';
        nodeFilters.forEach(function (b) { b.classList.toggle('is-active', (b.dataset.mapFilter || 'all') === 'all'); });
        linkFilters.forEach(function (b) { b.classList.toggle('is-active', (b.dataset.linkFilter || 'all') === 'all'); });
        graph.nodes.forEach(function (node) { delete node.x; delete node.y; delete node.vx; delete node.vy; });
        render();
    });

    fetch(root.dataset.source, { credentials: 'same-origin' })
        .then(function (response) { return response.json(); })
        .then(function (data) {
            graph = data;
            if (questSelect) {
                graph.nodes
                    .filter(function (node) { return node.kind === 'quest'; })
                    .sort(function (a, b) { return a.label.localeCompare(b.label); })
                    .forEach(function (node) {
                        var option = document.createElement('option');
                        option.value = node.id;
                        option.textContent = node.label;
                        questSelect.appendChild(option);
                    });
            }
            loading.hidden = true;
            render();
        })
        .catch(function () {
            loading.textContent = 'Impossibile caricare la mappa.';
        });
    window.addEventListener('resize', render);
})();
