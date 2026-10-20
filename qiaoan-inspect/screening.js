/* Deterministic dark-line screening. No trained model or diagnostic confidence. */
function screenPixels(rgba, w, h, sensitivity=50) {
 const N=w*h, gray=new Float32Array(N), integral=new Float64Array((w+1)*(h+1));
 let mean=0, sharp=0, dark=0, bright=0;
 for(let i=0;i<N;i++){gray[i]=.299*rgba[i*4]+.587*rgba[i*4+1]+.114*rgba[i*4+2];mean+=gray[i];if(gray[i]<20)dark++;if(gray[i]>240)bright++;}
 for(let y=0;y<h;y++){let row=0;for(let x=0;x<w;x++){row+=gray[y*w+x];integral[(y+1)*(w+1)+x+1]=integral[y*(w+1)+x+1]+row;}}
 const mask=new Uint8Array(N),radius=7,threshold=28-sensitivity*.20;
 for(let y=5;y<h-5;y++)for(let x=5;x<w-5;x++){
  const p=y*w+x,v=gray[p],x0=Math.max(0,x-radius),y0=Math.max(0,y-radius),x1=Math.min(w,x+radius+1),y1=Math.min(h,y+radius+1);
  const avg=(integral[y1*(w+1)+x1]-integral[y0*(w+1)+x1]-integral[y1*(w+1)+x0]+integral[y0*(w+1)+x0])/((x1-x0)*(y1-y0));
  const gx=gray[p+1]-gray[p-1],gy=gray[p+w]-gray[p-w];sharp+=gx*gx+gy*gy;
  if(avg-v<threshold)continue;
  let ridge=0;for(const d of [2,4])for(const offset of [d,d*w,d*(w+1),d*(w-1)])ridge=Math.max(ridge,Math.min(gray[p-offset]-v,gray[p+offset]-v));
  if(ridge>threshold*.65)mask[p]=1;
 }
 const visited=new Uint8Array(N),queue=new Int32Array(N),regions=[];
 for(let i=0;i<N;i++)if(mask[i]&&!visited[i]){
  let head=0,tail=1,minX=w,minY=h,maxX=0,maxY=0,sum=0;queue[0]=i;visited[i]=1;
  while(head<tail){const p=queue[head++],x=p%w,y=Math.floor(p/w);minX=Math.min(minX,x);maxX=Math.max(maxX,x);minY=Math.min(minY,y);maxY=Math.max(maxY,y);sum+=gray[p];
   for(let dy=-2;dy<=2;dy++)for(let dx=-2;dx<=2;dx++){if(!dx&&!dy)continue;const xx=x+dx,yy=y+dy,q=yy*w+xx;if(xx>=0&&xx<w&&yy>=0&&yy<h&&mask[q]&&!visited[q]){visited[q]=1;queue[tail++]=q;}}
  }
  const bw=maxX-minX+1,bh=maxY-minY+1,long=Math.max(bw,bh),short=Math.min(bw,bh);
  if(tail>=10&&long>=14&&long/short>=1.5&&tail/(bw*bh)<.8&&bw*bh<N*.35)regions.push({box:[Math.max(0,(minX-3)/w),Math.max(0,(minY-3)/h),Math.min(1,(maxX+4)/w),Math.min(1,(maxY+4)/h)],pixels:tail,label:'暗线候选',status:'待复核',source:'本地图像初筛'});
 }
 regions.sort((a,b)=>b.pixels-a.pixels);
 return {regions:regions.slice(0,40),total:regions.length,quality:{brightness:Math.round(mean/N),textureEnergy:Math.round(sharp/N),darkFraction:dark/N,brightFraction:bright/N},method:'暗线局部对比 + 连通区域筛选',analysisWidth:w,analysisHeight:h};
}
if(typeof module!=='undefined')module.exports={screenPixels};
