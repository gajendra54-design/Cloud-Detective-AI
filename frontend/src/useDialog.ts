import {useEffect,useRef} from 'react';
export function useDialog(active:boolean,onClose:()=>void){
 const close=useRef(onClose);close.current=onClose;
 useEffect(()=>{
  if(!active)return;
  const previous=document.activeElement as HTMLElement|null;
  const dialogs=document.querySelectorAll<HTMLElement>('[role="dialog"]');
  const dialog=dialogs.item(dialogs.length-1);
  if(!dialog)return;
  const nodes=()=>Array.from(dialog.querySelectorAll<HTMLElement>('button:not(:disabled),input,select,a[href],summary,[tabindex="0"]'));
  nodes()[0]?.focus();
  const handler=(event:KeyboardEvent)=>{
   if(event.key==='Escape'){event.preventDefault();close.current();return}
   if(event.key!=='Tab')return;
   const elements=nodes(),first=elements[0],last=elements[elements.length-1];
   if(event.shiftKey&&document.activeElement===first){event.preventDefault();last?.focus()}
   else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus()}
  };
  document.addEventListener('keydown',handler);
  const before=document.body.style.overflow;document.body.style.overflow='hidden';
  return()=>{document.removeEventListener('keydown',handler);document.body.style.overflow=before;previous?.focus()};
 },[active]);
}
