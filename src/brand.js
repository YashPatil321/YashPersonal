/**
 * Event branding. Change these to re-theme the site for another event.
 */
export const BRAND = {
    /** Short wordmark shown in the header and hero. */
    short: 'SACS',
    /** Default tournament name used by the setup wizard. */
    eventName: 'SACS Pickleball Tournament',
    /** Who is putting the event on. */
    organizer: 'South Asian Culture Show',
    tagline: 'Play for a cause',
    /** Shown on the landing page before the draw is published. */
    courts: 10,
    /** Used to plan the schedule only; not shown to players. */
    hours: 4,
    /** When the event is, as shown to players. */
    when: 'November 29, starting at 11am',
    /** ISO date the setup wizard starts with. */
    date: '2026-11-29',
    /** The only divisions. */
    divisions: ['Adults', 'Kids/Teens'],
    /** Every team plays at least this many games (the default draw guarantees it). */
    minGames: 3,
    /**
     * Optional GoFundMe (or other donation page) for extra donations from people who
     * aren't playing. Shows a "Donate" button next to the cause when set.
     * Keep the required $20 sign-up donations on Zelle/Venmo/cash: GoFundMe's terms
     * don't allow giving event entry in exchange for donations.
     */
    donateUrl: '',
    /** Required donation and where to send it. Shown on the Register tab; leave '' to hide a line. */
    payment: {
        fee: '$20 per person (required)',
        /** Required donation in dollars PER PLAYER (a pair gives twice this). */
        feeAmount: 20,
        zelle: 'sacsexec@gmail.com',
        venmo: '@SACS-2k27',
    },
    charity: {
        name: 'Akshaya Patra Foundation',
        url: 'https://apusa.org/',
        /** One-line description of the cause. */
        blurb: 'Akshaya Patra serves free, nutritious school lunches to children across India, so they can stay in class and learn.',
        pledge: 'A portion of every donation goes to the Akshaya Patra Foundation.',
    },
};
