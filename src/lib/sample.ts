import { toCSV } from './csv';

const FIRST = [
  'Alex', 'Jordan', 'Sam', 'Chris', 'Taylor', 'Morgan', 'Casey', 'Riley', 'Jamie', 'Drew', 'Avery', 'Quinn',
  'Reese', 'Skyler', 'Parker', 'Rowan', 'Hayden', 'Emerson', 'Dakota', 'Finley', 'Harper', 'Logan', 'Peyton', 'Sage',
  'Kendall', 'Blake', 'Cameron', 'Elliot', 'Jesse', 'Marley', 'Robin', 'Shawn', 'Toni', 'Devon', 'Kai', 'Lane',
];
const LAST = [
  'Kim', 'Lee', 'Patel', 'Garcia', 'Nguyen', 'Smith', 'Johnson', 'Brown', 'Chen', 'Lopez', 'Davis', 'Martin',
  'Wilson', 'Clark', 'Lewis', 'Walker', 'Young', 'Allen', 'King', 'Wright', 'Scott', 'Green', 'Baker', 'Adams',
  'Nelson', 'Hill', 'Ramirez', 'Campbell', 'Mitchell', 'Roberts', 'Carter', 'Phillips', 'Evans', 'Turner', 'Torres', 'Parker',
];

/** A realistic Google Form export: mutual partners, partners who didn't register, and free agents. */
export function sampleRegistrations(): string[][] {
  const header = [
    'Timestamp',
    'Email Address',
    'Full Name',
    'Phone Number',
    'Skill Level (DUPR or self-rating)',
    'Division',
    "Partner's Name (leave blank if you need one)",
  ];
  const rows: string[][] = [header];
  let n = 0;
  const day = new Date('2026-10-01T09:00:00');
  const person = () => {
    const i = n++;
    const name = `${FIRST[i % FIRST.length]} ${LAST[(i * 7) % LAST.length]}`;
    return { name, email: `${name.toLowerCase().replace(/ /g, '.')}@example.com`, phone: `555-01${String(i).padStart(2, '0')}` };
  };
  const stamp = () => {
    day.setMinutes(day.getMinutes() + 37);
    return day.toLocaleString('en-US');
  };
  const divisions: Array<{ name: string; skills: string[]; mutual: number; solo: number; free: number }> = [
    { name: 'Intermediate (3.0-3.5)', skills: ['3.0', '3.25', '3.5', 'Intermediate', '3.0 - 3.5'], mutual: 5, solo: 3, free: 4 },
    { name: 'Advanced (4.0+)', skills: ['4.0', '4.25', '4.5', 'DUPR 4.12', 'Advanced'], mutual: 4, solo: 2, free: 2 },
  ];
  for (const d of divisions) {
    const skill = () => d.skills[n % d.skills.length];
    for (let i = 0; i < d.mutual; i++) {
      const a = person();
      const b = person();
      rows.push([stamp(), a.email, a.name, a.phone, skill(), d.name, b.name]);
      rows.push([stamp(), b.email, b.name, b.phone, skill(), d.name, a.name]);
    }
    for (let i = 0; i < d.solo; i++) {
      const a = person();
      const b = person();
      rows.push([stamp(), a.email, a.name, a.phone, skill(), d.name, b.name]);
    }
    for (let i = 0; i < d.free; i++) {
      const a = person();
      rows.push([stamp(), a.email, a.name, a.phone, skill(), d.name, i % 2 ? 'Need a partner' : '']);
    }
  }
  return rows;
}

export function sampleCSV(): string {
  return toCSV(sampleRegistrations());
}
