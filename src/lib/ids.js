let counter = 0;
/** Short, collision-resistant id (good enough for a single tournament). */
export function uid(prefix = '') {
    counter = (counter + 1) % 1296;
    const rand = Math.random().toString(36).slice(2, 8);
    const time = Date.now().toString(36).slice(-4);
    return `${prefix}${time}${rand}${counter.toString(36).padStart(2, '0')}`;
}
export function shuffle(items, random = Math.random) {
    const arr = items.slice();
    for (let i = arr.length - 1; i > 0; i--) {
        const j = Math.floor(random() * (i + 1));
        [arr[i], arr[j]] = [arr[j], arr[i]];
    }
    return arr;
}
/** Deterministic PRNG for reproducible tests. */
export function seededRandom(seed) {
    let s = seed >>> 0;
    return () => {
        s = (s + 0x6d2b79f5) >>> 0;
        let t = s;
        t = Math.imul(t ^ (t >>> 15), t | 1);
        t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
}
