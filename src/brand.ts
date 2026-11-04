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
  hours: 4,
  /** Entry fee and where to send it. Shown on the Register tab; leave '' to hide a line. */
  payment: {
    fee: '', // e.g. '$20 per team'
    zelle: '', // e.g. 'sacsexec@gmail.com' or a phone number
    venmo: '', // e.g. '@SACS-Pickleball'
  },
  charity: {
    name: 'Akshaya Patra Foundation',
    url: 'https://www.akshayapatrausa.org/',
    /** One-line description of the cause. */
    blurb: 'Akshaya Patra serves free, nutritious school lunches to children across India, so they can stay in class and learn.',
    pledge: 'A portion of every entry fee is donated to the Akshaya Patra Foundation.',
  },
};
