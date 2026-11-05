import Image from 'next/image';
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
export default function CareerGallery() {
 return <section className={s.gallery} aria-labelledby="career-gallery-title">
  <div className={s.heading}><div><p className={s.eyebrow}>DIFFERENT SKILLS. A SHARED NEXT STEP.</p><h2 id="career-gallery-title">A place for <em>your kind of work.</em></h2><p>From practical trades to technical professions, start with the experience you already have.</p></div></div>
  {[careers.slice(0,15),careers.slice(15)].map((row,index)=><div className={s.viewport} key={index} aria-label={index===0?'Professional career examples':'Practical and service career examples'} tabIndex={0}><div className={`${s.track} ${index===1?s.reverse:''}`}>
   {[false,true].map(duplicate=><ul className={s.group} aria-hidden={duplicate||undefined} key={String(duplicate)}>{row.map(career=><li key={career.label}><figure className={s.card}><Image src={career.image} alt={duplicate?'':`${career.label}. Illustrative career portrait`} fill sizes="(max-width: 600px) 160px, 208px"/><figcaption>{career.label}</figcaption></figure></li>)}</ul>)}
  </div></div>)}
 </section>;
}
