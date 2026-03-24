(function () {
    function getNavbarOffset() {
        var navbar = document.querySelector('.app-top-navbar');
        if (!navbar) {
            return;
        }

        var height = Math.ceil(navbar.getBoundingClientRect().height);
        document.documentElement.style.setProperty('--nav-offset', height + 'px');
    }

    function initNavbarOffsetSync() {
        getNavbarOffset();
        window.addEventListener('resize', getNavbarOffset);

        if (window.ResizeObserver) {
            var navbar = document.querySelector('.app-top-navbar');
            if (navbar) {
                var observer = new ResizeObserver(getNavbarOffset);
                observer.observe(navbar);
            }
        }

        if (document.fonts && document.fonts.ready) {
            document.fonts.ready.then(getNavbarOffset).catch(function () {
                getNavbarOffset();
            });
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initNavbarOffsetSync);
    } else {
        initNavbarOffsetSync();
    }
})();
