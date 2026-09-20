/* Pure discovery logic shared by the library, worker, and tests. */
(function(root){
  'use strict';
  const version='minilm-v1';
  const descriptions={
    'Learning':['A tutorial or course to learn a skill, with lessons and exercises.','An educational guide explaining how something works.','Books and learning resources for studying a topic.'],
    'Read later':['An interesting long article, essay, research paper or book to read later.','A detailed thread explaining ideas worth taking time to read.'],
    'Build something':['A developer tool, library, open source repository or API for building a software project.','A practical project idea, code example or application to build.','Tools for creating a website, app, portfolio or prototype.'],
    'Job search':['A company is hiring: a job vacancy, internship or career opportunity.','Advice about resumes, interviews, recruiting, networking and finding a job.'],
    'Informative':['News, research findings, facts or analysis explaining a topic.','An informative explanation with practical advice or useful information.'],
    'Funny':['A joke, funny meme, punchline or humorous observation.','A comedy post making fun of a relatable situation.']
  };
  const cues={
    'Learning':/\b(tutorial|course|learn|guide|lesson|textbook|curriculum|explained)\b/i,
    'Read later':/\b(essay|article|paper|thread|book|long.read)\b/i,
    'Build something':/\b(github|repository|open.source|api|sdk|library|framework|build|prototype|developer tool)\b/i,
    'Job search':/\b(hiring|resume|résumé|interview|recruit|job|internship|career|vacancy)\b/i,
    'Informative':/\b(research|study|analysis|findings|explains|evidence)\b/i,
    'Funny':/\b(lmao|lol|joke|meme|hilarious|comedy)\b/i
  };
  function text(p){return [p.text,p.context,p.quotedPost?.text,...(p.media||[]).map(m=>m.alt)].filter(Boolean).join('\n').trim();}
  function fingerprint(p){let a=2166136261,b=5381;for(const c of text(p)){a=Math.imul(a^c.charCodeAt(0),16777619);b=Math.imul(b,33)^c.charCodeAt(0);}return `${version}:${(a>>>0).toString(16)}:${(b>>>0).toString(16)}`;}
  function chunks(value){const words=value.split(/\s+/).filter(Boolean), out=[];for(let i=0;i<words.length;i+=90)out.push(words.slice(i,i+120).join(' '));return out;}
  function cosine(a,b){let sum=0;for(let i=0;i<a.length;i++)sum+=a[i]*b[i];return sum;}
  function lexical(p,query){const hay=[text(p),p.author,p.authorName,p.note,...(p.links||[]),...(p.reasons||[])].join(' ').toLowerCase();const words=query.toLowerCase().match(/[\p{L}\p{N}_]+/gu)||[];return words.length?words.filter(w=>hay.includes(w)).length/words.length:0;}
  function suggestions(p,vectors,prototypes){
    if(text(p).length<25)return [];
    return Object.entries(descriptions).map(([label])=>{
      const similarity=Math.max(...vectors.flatMap(v=>prototypes[label].map(proto=>cosine(v,proto))));
      const cue=cues[label].test(text(p)+' '+(p.links||[]).join(' '));
      return {label,score:similarity+(cue?.09:0),evidence:cue?'Text contains a related topic or resource term.':'Saved text is similar to examples of this category.'};
    }).filter(s=>s.score>=(s.label==='Funny'?.43:.34)).sort((a,b)=>b.score-a.score).slice(0,3);
  }
  function labels(p,index){return [...new Set([...(p.reasons||[]),...(index?.suggestions||[]).map(s=>s.label).filter(s=>!(p.rejectedReasons||[]).includes(s))])];}
  function priority(p,index,focus=''){
    const tags=labels(p,index), why=[];let score=0;
    if(focus&&tags.includes(focus)){score+=10;why.push(`Matches ${focus.toLowerCase()}`);}
    if(p.sources.includes('bookmarks')){score+=2;why.push('You bookmarked it');}
    if((p.links||[]).some(u=>{try{return !['x.com','twitter.com','t.co'].includes(new URL(u).hostname);}catch{return false;}})){score+=3;why.push('Includes an external resource');}
    if(tags.some(t=>['Learning','Build something','Job search'].includes(t))){score+=2;why.push('May help you learn, build or find work');}
    if(text(p).length>150)score+=1;
    if(!why.length)why.push('An unreviewed save to rediscover');
    return {score,why:why.slice(0,2).join(' · ')};
  }
  function queue(posts,index,focus='',skipped=new Set()){
    const sorted=posts.filter(p=>p.status==='inbox'&&!skipped.has(p.key)&&(!focus||labels(p,index.get(p.key)).includes(focus))).sort((a,b)=>priority(b,index.get(b.key),focus).score-priority(a,index.get(a.key),focus).score||a.key.localeCompare(b.key));
    const result=[],authors=new Set(),deferred=[];
    for(const p of sorted){if(authors.has(p.author))deferred.push(p);else{authors.add(p.author);result.push(p);}}
    return [...result,...deferred];
  }
  const api={version,descriptions,text,fingerprint,chunks,cosine,lexical,suggestions,labels,priority,queue};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.GoldDiscovery=api;
})(globalThis);
