import Image from 'next/image';
import Link from 'next/link';
import { ArrowUpRight, Fingerprint, Globe2, ShieldCheck } from 'lucide-react';
import s from '@/app/career-gallery.module.css';

const careers = [
  {
    "label": "Doctor",
    "image": "/careers/doctor.webp"
  },
  {
    "label": "Nurse",
    "image": "/careers/nurse.webp"
  },
  {
    "label": "Pharmacist",
    "image": "/careers/pharmacist.webp"
  },
  {
    "label": "Dentist",
    "image": "/careers/dentist.webp"
  },
  {
    "label": "Care worker",
    "image": "/careers/care-worker.webp"
  },
  {
    "label": "Laboratory technician",
    "image": "/careers/laboratory-technician.webp"
  },
  {
    "label": "Software engineer",
    "image": "/careers/software-engineer.webp"
  },
  {
    "label": "Data analyst",
    "image": "/careers/data-analyst.webp"
  },
  {
    "label": "Civil engineer",
    "image": "/careers/civil-engineer.webp"
  },
  {
    "label": "Architect",
    "image": "/careers/architect.webp"
  },
  {
    "label": "Accountant",
    "image": "/careers/accountant.webp"
  },
  {
    "label": "Teacher",
    "image": "/careers/teacher.webp"
  },
  {
    "label": "Graphic designer",
    "image": "/careers/graphic-designer.webp"
  },
  {
    "label": "Mechanical engineer",
    "image": "/careers/mechanical-engineer.webp"
  },
  {
    "label": "Electrical engineer",
    "image": "/careers/electrical-engineer.webp"
  },
  {
    "label": "Bus driver",
    "image": "/careers/bus-driver.webp"
  },
  {
    "label": "Delivery driver",
    "image": "/careers/delivery-driver.webp"
  },
  {
    "label": "Plumber",
    "image": "/careers/plumber.webp"
  },
  {
    "label": "Electrician",
    "image": "/careers/electrician.webp"
  },
  {
    "label": "Carpenter",
    "image": "/careers/carpenter.webp"
  },
  {
    "label": "Welder",
    "image": "/careers/welder.webp"
  },
  {
    "label": "Construction worker",
    "image": "/careers/construction-worker.webp"
  },
  {
    "label": "Site supervisor",
    "image": "/careers/site-supervisor.webp"
  },
  {
    "label": "Vehicle mechanic",
    "image": "/careers/vehicle-mechanic.webp"
  },
  {
    "label": "Chef",
    "image": "/careers/chef.webp"
  },
  {
    "label": "Cook",
    "image": "/careers/cook.webp"
  },
  {
    "label": "Waiter",
    "image": "/careers/waiter.webp"
  },
  {
    "label": "Baker",
    "image": "/careers/baker.webp"
  },
  {
    "label": "Warehouse operative",
    "image": "/careers/warehouse-operative.webp"
  },
  {
    "label": "Hotel receptionist",
    "image": "/careers/hotel-receptionist.webp"
  }
];

const sourceItems = [
  { icon: ShieldCheck, label: 'UK sponsor register' },
  { icon: Fingerprint, label: 'Matched to your background' },
  { icon: Globe2, label: 'Available employer contacts' },
];

export default function CareerGallery() {
  return (
    <section className={s.gallery} aria-label="Career examples and research sources">
      {[careers.slice(0, 15), careers.slice(15)].map((row, index) => (
        <div className={s.viewport} key={index} tabIndex={0} role="region" aria-label={index === 0 ? 'Professional career examples' : 'Practical and service career examples'}>
          <div className={`${s.track} ${index === 1 ? s.reverse : ''}`}>
            {[false, true].map(duplicate => (
              <ul className={s.group} aria-hidden={duplicate || undefined} key={String(duplicate)}>
                {row.map(career => (
                  <li key={career.label}>
                    <figure className={s.card}>
                      <Image src={career.image} alt="" fill sizes="(max-width: 600px) 125px, 180px"/>
                      <figcaption>{career.label}</figcaption>
                    </figure>
                  </li>
                ))}
              </ul>
            ))}
          </div>
        </div>
      ))}
      <div className={s.ribbon}>
        <div className={s.ribbonTrack}>
          {[false, true].map(duplicate => (
            <div className={s.ribbonGroup} key={String(duplicate)} aria-hidden={duplicate || undefined}>
              {sourceItems.map(({icon: Icon, label}) => <span key={label}><Icon size={17}/> {label}</span>)}
              <Link href="/our-data" tabIndex={duplicate ? -1 : undefined}>How we use sources <ArrowUpRight size={15}/></Link>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
