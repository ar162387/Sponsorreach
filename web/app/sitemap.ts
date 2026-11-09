import type { MetadataRoute } from 'next';
export default function sitemap(): MetadataRoute.Sitemap { return ['', '/our-data', '/disclaimer', '/terms', '/privacy', '/data-deletion', '/refunds', '/contact'].map(path=>({url:'https://sponsorreach.uk'+path})); }
