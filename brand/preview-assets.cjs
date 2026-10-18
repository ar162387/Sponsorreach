const path=require('node:path');const sharp=require(path.resolve(__dirname,'../web/node_modules/sharp'));
const dir=path.resolve(__dirname,'../web/public/brand');
async function main(){
const panels=Buffer.from(`<svg width="1400" height="1020" xmlns="http://www.w3.org/2000/svg"><rect width="1400" height="1020" fill="#FAFBF8"/><rect x="720" y="88" width="630" height="200" rx="16" fill="#062D45"/><rect x="720" y="334" width="630" height="292" rx="16" fill="#062D45"/><g font-family="Arial,sans-serif" fill="#0B3B5B"><text x="50" y="45" font-size="26" font-weight="bold">SponsorReach UK · transparent logo pack</text><text x="50" y="100" font-size="17">Horizontal · light backgrounds</text><text x="50" y="333" font-size="17">Stacked · brand applications</text><text x="50" y="685" font-size="17">Colour mark</text><text x="395" y="685" font-size="17">Navy monochrome</text><text x="760" y="685" font-size="17">White monochrome</text><text x="50" y="927" font-size="17">Favicons at actual size: 16 px · 32 px · 64 px</text></g><g font-family="Arial,sans-serif" fill="white" font-size="17"><text x="750" y="125">White + teal · dark backgrounds</text><text x="750" y="375">Compact white + teal mark</text></g><rect x="720" y="700" width="630" height="185" rx="16" fill="#062D45"/></svg>`);
const comps=[{input:panels,left:0,top:0}];
for(const [file,w,h,x,y] of [['logo-horizontal.png',600,130,50,130],['logo-reversed.png',560,110,750,150],['logo-stacked.png',560,240,50,360],['sr-mark-reversed.png',400,180,800,408],['sr-mark.png',240,150,50,717],['sr-mark-navy.png',240,150,390,717],['sr-mark-white.png',300,140,820,722]]){
comps.push({input:await sharp(path.join(dir,file)).resize(w,h,{fit:'inside'}).png().toBuffer(),left:x,top:y});
}
for(const [s,x] of [[16,50],[32,100],[64,170]])comps.push({input:await sharp(path.join(dir,'favicon-'+s+'.png')).toBuffer(),left:x,top:948});
await sharp({create:{width:1400,height:1020,channels:4,background:'#FAFBF8'}}).composite(comps).png().toFile(path.join(__dirname,'logo-pack-preview.png'));
}
main();
