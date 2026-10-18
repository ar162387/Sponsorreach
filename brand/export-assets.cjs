/* Reproducible asset exports. Run from sponsormatch/web with `node ../brand/export-assets.cjs`.
   ImageGen produced the colour originals; precise white recolouring was authorised by the user. */
const path=require('node:path');
const fs=require('node:fs/promises');
const sharp=require(path.resolve(__dirname,'../web/node_modules/sharp'));
const brand=path.resolve(__dirname,'../web/public/brand');

async function recolour(source,destination,allWhite=false){
  const {data,info}=await sharp(path.join(brand,source)).ensureAlpha().raw().toBuffer({resolveWithObject:true});
  for(let i=0;i<data.length;i+=4){
    const isTeal=data[i+1]>data[i]*1.5 && data[i+1]>data[i+2]*.8 && data[i+1]>90;
    if(allWhite || !isTeal){data[i]=255;data[i+1]=255;data[i+2]=255;}
  }
  await sharp(data,{raw:{width:info.width,height:info.height,channels:4}}).png().toFile(path.join(brand,destination));
}
async function main(){
  await recolour('sr-mark.png','sr-mark-reversed.png');
  await recolour('sr-mark.png','sr-mark-white.png',true);
  await recolour('logo-horizontal.png','logo-reversed.png');
  for(const [name,size] of [['favicon-16.png',16],['favicon-32.png',32],['favicon-64.png',64],['apple-touch-icon.png',180]]){
    await sharp(path.join(brand,'sr-mark.png')).resize(size,size,{fit:'contain',background:{r:0,g:0,b:0,alpha:0}}).png().toFile(path.join(brand,name));
  }
  await fs.copyFile(path.join(brand,'favicon-64.png'),path.resolve(__dirname,'../web/app/icon.png'));
  await fs.copyFile(path.join(brand,'apple-touch-icon.png'),path.resolve(__dirname,'../web/app/apple-icon.png'));
  await sharp(path.join(brand,'social-share-source.png')).resize(1200,630,{fit:'contain',background:'#FAFBF8'}).png().toFile(path.join(brand,'social-share.png'));
  const report=[];
  for(const name of ['logo-stacked.png','logo-horizontal.png','logo-reversed.png','sr-mark.png','sr-mark-reversed.png','sr-mark-navy.png','sr-mark-white.png']){
    const {data,info}=await sharp(path.join(brand,name)).ensureAlpha().raw().toBuffer({resolveWithObject:true});
    let clear=0,visible=0;for(let i=3;i<data.length;i+=4){if(data[i]===0)clear++;else visible++;}
    if(!clear||!visible)throw new Error(`Missing genuine transparent alpha or visible artwork: ${name}`);
    report.push({name,width:info.width,height:info.height,transparent_pixels:clear,visible_pixels:visible});
  }
  for(const [a,b] of [['sr-mark.png','sr-mark-white.png'],['sr-mark.png','sr-mark-reversed.png'],['logo-horizontal.png','logo-reversed.png']]){
    const first=await sharp(path.join(brand,a)).ensureAlpha().raw().toBuffer();
    const second=await sharp(path.join(brand,b)).ensureAlpha().raw().toBuffer();
    if(first.length!==second.length)throw new Error('Variant dimensions changed');
    for(let i=3;i<first.length;i+=4)if(first[i]!==second[i])throw new Error(`Transparency changed: ${b}`);
  }
  await fs.writeFile(path.join(__dirname,'ASSET_VERIFICATION.json'),JSON.stringify({alpha_preserved_for_recoloured_variants:true,assets:report},null,2)+'\n');
  console.log(JSON.stringify(report,null,2));
}
main().catch(e=>{console.error(e);process.exitCode=1;});
