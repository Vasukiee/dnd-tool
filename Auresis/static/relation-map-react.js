(function () {
    var mount = document.querySelector('[data-relation-react-overlay]');
    if (!mount || !window.React || !window.ReactDOM) return;

    var e = window.React.createElement;
    var source = mount.dataset.source;

    function bucket(nodes, kind) {
        return nodes.filter(function (node) { return node.kind === kind; }).length;
    }

    function RelationSignal() {
        var state = window.React.useState({ loading: true, nodes: [], links: [] });
        var data = state[0];
        var setData = state[1];

        window.React.useEffect(function () {
            var alive = true;
            fetch(source, { credentials: 'same-origin' })
                .then(function (response) { return response.json(); })
                .then(function (payload) {
                    if (alive) setData({ loading: false, nodes: payload.nodes || [], links: payload.links || [] });
                })
                .catch(function () {
                    if (alive) setData({ loading: false, nodes: [], links: [] });
                });
            return function () { alive = false; };
        }, []);

        if (data.loading) {
            return e('div', { className: 'relation-signal relation-signal--loading' },
                e('p', { className: 'relation-signal__eyebrow' }, 'Segnale'),
                e('div', { className: 'relation-signal__scan' })
            );
        }

        var nodes = data.nodes;
        var links = data.links;
        var max = Math.max(1, nodes.length);
        var rows = [
            ['npc', 'NPC', bucket(nodes, 'npc')],
            ['quest', 'Incarichi', bucket(nodes, 'quest')],
            ['luogo', 'Luoghi', bucket(nodes, 'luogo')],
            ['fazione', 'Fazioni', bucket(nodes, 'fazione')]
        ];

        return e('div', { className: 'relation-signal' },
            e('p', { className: 'relation-signal__eyebrow' }, 'Segnale relazionale'),
            e('div', { className: 'relation-signal__pulse', 'aria-hidden': 'true' },
                e('span', null), e('span', null), e('span', null)
            ),
            e('div', { className: 'relation-signal__summary' },
                e('strong', null, nodes.length),
                e('span', null, 'nodi monitorati'),
                e('em', null, links.length + ' legami')
            ),
            e('div', { className: 'relation-signal__bars' }, rows.map(function (row) {
                return e('div', { className: 'relation-signal__bar relation-signal__bar--' + row[0], key: row[0] },
                    e('span', null, row[1]),
                    e('i', { style: { '--signal-width': Math.max(8, Math.round((row[2] / max) * 100)) + '%' } }),
                    e('b', null, row[2])
                );
            }))
        );
    }

    window.ReactDOM.createRoot(mount).render(e(RelationSignal));
})();
