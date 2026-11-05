import type { MetadataRoute } from 'next';
export default function robots(): MetadataRoute.Robots { return {rules:{userAgent:'*',allow:'/',disallow:['/api/','/account','/admin','/results/','/match']},sitemap:'https://sponsorreach.uk/sitemap.xml'}; }
