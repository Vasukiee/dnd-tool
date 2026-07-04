(function () {
    if (!window.React || !window.ReactDOM) return;
    var mount = document.getElementById('react-motion-root');
    if (!mount) return;

    var e = window.React.createElement;
    var routeLabels = [
        ['mappa-relazioni', 'Mappa relazionale'],
        ['quest', 'Incarichi'],
        ['npc', 'Personaggi'],
        ['locations', 'Luoghi'],
        ['fazioni', 'Fazioni'],
        ['eventi', 'Cronaca'],
        ['indagini', 'Indagini'],
        ['audio', 'Audio'],
        ['', 'Cabina di regia']
    ];

    function currentLabel() {
        var path = window.location.pathname.replace(/^\//, '');
        for (var i = 0; i < routeLabels.length; i += 1) {
            if (routeLabels[i][0] === '' || path.indexOf(routeLabels[i][0]) === 0) return routeLabels[i][1];
        }
        return 'Registro';
    }

    function MotionLayer() {
        window.React.useEffect(function () {
            document.documentElement.classList.add('has-react-motion');
        }, []);

        var motes = [0, 1, 2, 3, 4, 5, 6, 7];
        return e('div', { className: 'react-motion' },
            e('div', { className: 'react-motion__spotlight' }),
            e('div', { className: 'react-motion__scanline' }),
            e('div', { className: 'react-motion__motes' }, motes.map(function (i) {
                return e('span', { key: i, style: { '--mote-index': i } });
            })),
            e('div', { className: 'react-motion__route' },
                e('span', null, 'Auresis'),
                e('strong', null, currentLabel())
            )
        );
    }

    window.ReactDOM.createRoot(mount).render(e(MotionLayer));
})();
