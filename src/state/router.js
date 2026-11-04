import { useEffect, useState } from 'react';
function parse() {
    const raw = window.location.hash.replace(/^#/, '') || '/';
    const [path, qs] = raw.split('?');
    return { path, parts: path.split('/').filter(Boolean), query: new URLSearchParams(qs ?? '') };
}
export function useRoute() {
    const [route, setRoute] = useState(parse);
    useEffect(() => {
        const onChange = () => {
            setRoute(parse());
            window.scrollTo({ top: 0 });
        };
        window.addEventListener('hashchange', onChange);
        return () => window.removeEventListener('hashchange', onChange);
    }, []);
    return route;
}
export function navigate(path) {
    window.location.hash = path.startsWith('#') ? path : `#${path}`;
}
