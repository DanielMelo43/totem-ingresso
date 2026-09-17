export type Movie = { id: string; title: string; genre: string; duration: string; rating: string; language: string; format: string; color: string; sessions: string[] }
export type Product = { id: string; name: string; description: string; price: number; category: string; icon: string }
export type TicketType = { id: string; name: string; detail: string; price: number }

const localIsoDate = (value:Date) => `${value.getFullYear()}-${String(value.getMonth()+1).padStart(2,'0')}-${String(value.getDate()).padStart(2,'0')}`
export const dates = Array.from({length:5},(_,offset)=>{
  const value=new Date(); value.setDate(value.getDate()+offset)
  const day=offset===0?'HOJE':value.toLocaleDateString('pt-BR',{weekday:'short'}).replace('.','').toUpperCase()
  return {label:`${day} ${value.toLocaleDateString('pt-BR',{day:'2-digit',month:'2-digit'})}`,date:localIsoDate(value)}
})
export const money = (v:number) => v.toLocaleString('pt-BR',{style:'currency',currency:'BRL'})
