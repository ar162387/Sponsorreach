import Image from 'next/image';
import Link from 'next/link';

export default function Brand({ inverse = false }: { inverse?: boolean }) {
  return <Link href="/" className={`brand${inverse ? ' brand-inverse' : ''}`} aria-label="SponsorReach UK home">
    <Image src={inverse ? '/brand/sr-mark-reversed.png' : '/brand/sr-mark.png'} width={56} height={48} alt="" className="brand-symbol"/>
    <span className="brand-wordmark">SponsorReach<span>UK</span></span>
  </Link>;
}
