// Tests set SHIKEN_TODAY=YYYY-MM-DD (Japan time) so that the pages are made for that day.  Without it, the clock is the real one.
if(process.env.SHIKEN_TODAY){
 const fixed=new (globalThis.Date)(process.env.SHIKEN_TODAY+'T09:00:00+09:00').getTime();
 const Real=globalThis.Date;
 globalThis.Date=class extends Real{constructor(...a){if(a.length===0)super(fixed);else super(...a);}static now(){return fixed;}};
}
