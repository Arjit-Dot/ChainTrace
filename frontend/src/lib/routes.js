// Every route in one place. Three areas: the gateway (/), the citizen side (/citizen/...) and the officer console
// (/officer/...). Pages and components build their links from here so a path is never typed twice.
export const R = {
  gateway: '/',
  citizen: '/citizen',
  file: '/citizen/file',
  submitted: (id) => `/citizen/submitted/${encodeURIComponent(id)}`,
  track: '/citizen/track',
  officer: '/officer',
  officerCase: (id) => `/officer/cases/${encodeURIComponent(id)}`,
  officerNetworks: '/officer/networks',
  officerNetwork: (id) => `/officer/networks?id=${encodeURIComponent(id)}`,
}
