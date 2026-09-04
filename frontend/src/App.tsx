import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { dates, money, type Movie, type Product, type TicketType } from './data'
import { apiMutation, apiRequest, PublicApiError } from './security'

type Step = 'home'|'seats'|'tickets'|'food'|'identify'|'payment'|'success'
type Counts = Record<string,number>
type Reservation = {id:string;showtime_id:string;seats:string[];expires_at:string}
type ApiOrder = {id:string;status:string}
type ApiShowtime = {id:string;starts_at:string;room:string;movie:{id:string;title:string;genre:string;duration_minutes:number;rating:string;language:string;format:string;color:string}}
const flow: Step[] = ['seats','tickets','food','payment','success']
const labels = ['Assentos','Ingressos','Bomboniere','Pagamento','Confirmação']

function Icon({name}:{name:string}) { const map:Record<string,string>={seats:'▦',tickets:'🎟',food:'🍿',payment:'▣',success:'✓'}; return <span>{map[name]}</span> }

function Stepper({step}:{step:Step}) {
  const current = step==='identify'?3:Math.max(0,flow.indexOf(step))
  return <div className="stepper">{flow.map((s,i)=><div className={`step ${i<=current?'done':''} ${i===current?'active':''}`} key={s}><div className="step-dot"><Icon name={s}/></div><span>{labels[i]}</span></div>)}</div>
}

function Poster({movie,large=false}:{movie:Movie;large?:boolean}) { return <div className={`poster ${large?'large':''}`} style={{'--poster':movie.color} as React.CSSProperties}><small>UMA HISTÓRIA INESQUECÍVEL</small><strong>{movie.title}</strong><span>EM CARTAZ</span></div> }

function Counter({value,onChange,max=20}:{value:number;onChange:(v:number)=>void;max?:number}) { return <div className="counter"><button onClick={()=>onChange(Math.max(0,value-1))} aria-label="Diminuir">−</button><b>{value}</b><button onClick={()=>onChange(Math.min(max,value+1))} aria-label="Aumentar">+</button></div> }

function Modal({title,children,action,onClose}:{title:string;children:React.ReactNode;action:string;onClose:()=>void}) { return <div className="overlay"><div className="modal"><div className="alert-icon">!</div><h2>{title}</h2><p>{children}</p><button className="primary full" onClick={onClose}>{action}</button></div></div> }

function VirtualKeyboard({numeric,onKey}:{numeric?:boolean;onKey:(key:string)=>void}) {
 const keys=numeric?['1','2','3','4','5','6','7','8','9','0','⌫']:['1','2','3','4','5','6','7','8','9','0','Q','W','E','R','T','Y','U','I','O','P','A','S','D','F','G','H','J','K','L','Z','X','C','V','B','N','M','@','.','⌫']
 return <div className={`keyboard ${numeric?'numeric':''}`}>{keys.map(k=><button key={k} onClick={()=>onKey(k)}>{k}</button>)}</div>
}

function formatCpf(value:string) {
 const digits=value.replace(/\D/g,'').slice(0,11)
 return digits.replace(/^(\d{3})(\d)/,'$1.$2').replace(/^(\d{3})\.(\d{3})(\d)/,'$1.$2.$3').replace(/\.(\d{3})(\d)/,'.$1-$2')
}

function isValidCpf(value:string) {
 const cpf=value.replace(/\D/g,'')
 if(cpf.length!==11 || /^(\d)\1{10}$/.test(cpf)) return false
 const digit=(length:number)=>{
   let sum=0
   for(let i=0;i<length;i++) sum+=Number(cpf[i])*(length+1-i)
   const result=(sum*10)%11
   return result===10?0:result
 }
 return digit(9)===Number(cpf[9]) && digit(10)===Number(cpf[10])
}

function isValidGmail(value:string) {
 const email=value.trim().toLowerCase()
 const [user,domain,...extra]=email.split('@')
 if(extra.length || domain!=='gmail.com' || !user || user.length>64) return false
 if(user.startsWith('.') || user.endsWith('.') || user.includes('..')) return false
 return /^[a-z0-9.]+$/.test(user)
}

function Header({step,onCancel}:{step:Step;onCancel:()=>void}) { return <><header><div className="brand"><span className="brandmark">T</span><div><b>CINE</b><small>INGRESSOS</small></div></div>{step!=='home'&&step!=='success'&&<button className="text-button" onClick={onCancel}>Cancelar compra</button>}</header>{step!=='home'&&<Stepper step={step}/>}</> }

function OrderSummary({movie,time,seats,tickets,cart,ticketTypes,products}:{movie:Movie;time:string;seats:string[];tickets:Counts;cart:Counts;ticketTypes:TicketType[];products:Product[]}) {
 const ticketTotal=ticketTypes.reduce((s,t)=>s+(tickets[t.id]||0)*t.price,0), foodTotal=products.reduce((s,p)=>s+(cart[p.id]||0)*p.price,0)
 return <aside className="summary"><h3>Resumo do pedido</h3><div className="movie-mini"><Poster movie={movie}/><div><b>{movie.title}</b><small>{movie.language} • {movie.format}</small><small>Sala 04 • {time}</small></div></div><div className="summary-section"><span>Assentos</span><b>{seats.length?seats.join(', '):'—'}</b></div>{ticketTypes.filter(t=>tickets[t.id]).map(t=><div className="line" key={t.id}><span>{tickets[t.id]}× {t.name}</span><b>{money(tickets[t.id]*t.price)}</b></div>)}{products.filter(p=>cart[p.id]).map(p=><div className="line" key={p.id}><span>{cart[p.id]}× {p.name}</span><b>{money(cart[p.id]*p.price)}</b></div>)}<div className="total"><span>Total</span><b>{money(ticketTotal+foodTotal)}</b></div></aside>
}

function App(){
 const [step,setStep]=useState<Step>('home'),[movie,setMovie]=useState<Movie>({id:'',title:'',genre:'',duration:'',rating:'',language:'',format:'',color:'#635bff',sessions:[]}),[time,setTime]=useState(''),[showtimeId,setShowtimeId]=useState(''),[showDate,setShowDate]=useState(dates[0].date),[seats,setSeats]=useState<string[]>([]),[tickets,setTickets]=useState<Counts>({}),[cart,setCart]=useState<Counts>({}),[customer,setCustomer]=useState<{kind:'cpf'|'email';value:string}|null>(null),[reservationId,setReservationId]=useState(''),[orderId,setOrderId]=useState(''),[seatBusy,setSeatBusy]=useState(false),[payBusy,setPayBusy]=useState(false),[modal,setModal]=useState(''),[idle,setIdle]=useState(false),[idleCount,setIdleCount]=useState(10)
 const orderKey=useRef(''),paymentKey=useRef('')
 const [catalogTickets,setCatalogTickets]=useState<TicketType[]>([]),[catalogProducts,setCatalogProducts]=useState<Product[]>([])
 const clearLocal=useCallback(()=>{setStep('home');setTime('');setShowtimeId('');setSeats([]);setTickets({});setCart({});setCustomer(null);setReservationId('');setOrderId('');setIdle(false);orderKey.current='';paymentKey.current=''},[])
 const reset=useCallback(async()=>{try{if(orderId)await apiMutation(`/api/v1/orders/${orderId}/cancel`,{});else if(reservationId)await apiMutation(`/api/v1/reservations/${reservationId}/cancel`,{})}catch(error){if(import.meta.env.DEV)console.error(error)}finally{clearLocal()}},[orderId,reservationId,clearLocal])
 useEffect(()=>{if(step==='home'||step==='success')return; let warn:number, end:number; const restart=()=>{clearTimeout(warn);clearTimeout(end);warn=window.setTimeout(()=>{setIdle(true);setIdleCount(10)},50000);end=window.setTimeout(reset,60000)}; restart(); const events=['pointerdown','keydown'];events.forEach(e=>window.addEventListener(e,restart));return()=>{clearTimeout(warn);clearTimeout(end);events.forEach(e=>window.removeEventListener(e,restart))}},[step,reset])
 useEffect(()=>{if(!idle)return;const x=window.setInterval(()=>setIdleCount(n=>Math.max(0,n-1)),1000);return()=>clearInterval(x)},[idle])
 useEffect(()=>{Promise.all([apiRequest<TicketType[]>('/api/v1/ticket-types'),apiRequest<Product[]>('/api/v1/products')]).then(([types,items])=>{setCatalogTickets(types.map(item=>({...item,price:Number(item.price)})));setCatalogProducts(items.map(item=>({...item,price:Number(item.price)})))}).catch(()=>setModal('Não foi possível atualizar o catálogo. Verifique a conexão com o servidor.'))},[])
 const total=useMemo(()=>catalogTickets.reduce((s,t)=>s+(tickets[t.id]||0)*t.price,0)+catalogProducts.reduce((s,p)=>s+(cart[p.id]||0)*p.price,0),[tickets,cart,catalogTickets,catalogProducts])
 const selectSession=(m:Movie,t:string,date:string,id:string)=>{setMovie(m);setTime(t);setShowDate(date);setShowtimeId(id);setStep('seats')}
 const toggleSeat=async(id:string)=>{if(seatBusy)return;const next=seats.includes(id)?seats.filter(x=>x!==id):[...seats,id];setSeatBusy(true);try{if(!next.length&&reservationId){await apiMutation(`/api/v1/reservations/${reservationId}/cancel`,{});setReservationId('');setSeats([])}else{const result=await apiMutation<Reservation>('/api/v1/reservations',{showtime_id:showtimeId,seats:next,reservation_id:reservationId||null});setReservationId(result.id);setSeats(result.seats)}}catch(error){setModal(error instanceof PublicApiError?error.message:'Não foi possível reservar o assento.')}finally{setSeatBusy(false)}}
 const finishPayment=async(method:string)=>{if(!customer||payBusy)return;setPayBusy(true);try{if(!orderKey.current)orderKey.current=crypto.randomUUID();let currentOrder=orderId;if(!currentOrder){const order=await apiMutation<ApiOrder>('/api/v1/orders',{showtime_id:showtimeId,seats,tickets:Object.entries(tickets).filter(([,quantity])=>quantity).map(([id,quantity])=>({id,quantity})),products:Object.entries(cart).filter(([,quantity])=>quantity).map(([id,quantity])=>({id,quantity})),customer,reservation_id:reservationId},orderKey.current);currentOrder=order.id;setOrderId(order.id)}if(!paymentKey.current)paymentKey.current=crypto.randomUUID();await apiMutation<ApiOrder>(`/api/v1/orders/${currentOrder}/payment`,{method},paymentKey.current);setStep('success')}catch(error){setModal(error instanceof PublicApiError?error.message:'Não foi possível concluir o pagamento.')}finally{setPayBusy(false)}}
 return <div className="app"><Header step={step} onCancel={reset}/>{step==='home'&&<Home onSelect={selectSession}/>} {step!=='home'&&step!=='success'&&<main className="purchase"><section className="content">{step==='seats'&&<Seats showtimeId={showtimeId} selected={seats} onToggle={toggleSeat} busy={seatBusy} onNext={()=>seats.length?setStep('tickets'):setModal('Selecione ao menos um assento para continuar.')} onBack={reset}/>} {step==='tickets'&&<Tickets ticketTypes={catalogTickets} counts={tickets} setCounts={setTickets} seats={seats.length} onBack={()=>setStep('seats')} onNext={()=>Object.values(tickets).reduce((a,b)=>a+b,0)===seats.length?setStep('food'):setModal('Escolha os tipos de ingresso para todos os assentos selecionados.')} />} {step==='food'&&<Food products={catalogProducts} cart={cart} setCart={setCart} onBack={()=>setStep('tickets')} onNext={()=>setStep('identify')}/>} {step==='identify'&&<Identify onBack={()=>setStep('food')} onNext={value=>{setCustomer(value);setStep('payment')}}/>} {step==='payment'&&<Payment total={total} busy={payBusy} onBack={()=>setStep('identify')} onNext={finishPayment}/>}</section><OrderSummary movie={movie} time={time} seats={seats} tickets={tickets} cart={cart} ticketTypes={catalogTickets} products={catalogProducts}/></main>}{step==='success'&&<Success movie={movie} date={showDate} time={time} seats={seats} total={total} reset={clearLocal}/>} {modal&&<Modal title="Ops!" action="Entendi" onClose={()=>setModal('')}>{modal}</Modal>}{idle&&<Modal title="Ainda está aí?" action="Continuar comprando" onClose={()=>setIdle(false)}>Sua sessão será encerrada em {idleCount} segundos por inatividade.</Modal>}</div>
}

function Home({onSelect}:{onSelect:(m:Movie,t:string,date:string,id:string)=>void}){
 const [date,setDate]=useState(0),[filter,setFilter]=useState('Todos'),[catalogMovies,setCatalogMovies]=useState<Movie[]>([]),[sessionIds,setSessionIds]=useState<Record<string,string>>({}),[loading,setLoading]=useState(true),[loadError,setLoadError]=useState('')
 useEffect(()=>{let active=true;setLoading(true);setLoadError('');apiRequest<ApiShowtime[]>(`/api/v1/showtimes?on=${dates[date].date}`).then(showtimes=>{if(!active)return;const grouped=new Map<string,Movie>(),ids:Record<string,string>={};for(const session of showtimes){const hour=session.starts_at.slice(11,16);ids[`${session.movie.id}-${hour}`]=session.id;const current=grouped.get(session.movie.id);if(current)current.sessions.push(hour);else grouped.set(session.movie.id,{id:session.movie.id,title:session.movie.title,genre:session.movie.genre,duration:`${Math.floor(session.movie.duration_minutes/60)}h ${session.movie.duration_minutes%60}min`,rating:session.movie.rating,language:session.movie.language,format:session.movie.format,color:session.movie.color,sessions:[hour]})}setCatalogMovies([...grouped.values()]);setSessionIds(ids)}).catch(error=>{if(active)setLoadError(error instanceof PublicApiError?error.message:'Não foi possível carregar as sessões.')}).finally(()=>{if(active)setLoading(false)});return()=>{active=false}},[date])
 const visible=catalogMovies.filter(m=>filter==='Todos'||m.language===filter||m.format===filter)
 return <main className="home"><div className="hero"><div><span className="eyebrow">BEM-VINDO AO CINE</span><h1>Qual história você<br/>quer viver hoje?</h1><p>Escolha um filme e toque no melhor horário para começar.</p></div><div className="hero-orb">▶</div></div><div className="date-tabs">{dates.map((d,i)=>{const [day,value]=d.label.split(' ');return <button className={date===i?'selected':''} onClick={()=>setDate(i)} key={d.date}>{day}<b>{value}</b></button>})}</div><div className="section-title"><div><h2>Filmes em cartaz</h2><p>{loading?'Carregando sessões...':`${catalogMovies.length} filmes disponíveis`}</p>{loadError&&<p className="field-help error">{loadError}</p>}</div><div className="filters">{['Todos','Dublado','Nacional','3D'].map(f=><button className={filter===f?'selected':''} onClick={()=>setFilter(f)} key={f}>{f}</button>)}</div></div><div className="movie-grid">{visible.map(m=><article className="movie-card" key={m.id}><Poster movie={m} large/><div className="movie-info"><div className="rating">{m.rating}</div><h3>{m.title}</h3><p>{m.genre} • {m.duration}</p><div className="tags"><span>{m.format}</span><span>{m.language}</span></div><small>SESSÕES DISPONÍVEIS</small><div className="sessions">{m.sessions.map(t=><button onClick={()=>onSelect(m,t,dates[date].date,sessionIds[`${m.id}-${t}`])} key={t}>{t}</button>)}</div></div></article>)}</div></main>
}

function Seats({showtimeId,selected,onToggle,busy,onNext,onBack}:{showtimeId:string;selected:string[];onToggle:(id:string)=>void;busy:boolean;onNext:()=>void;onBack:()=>void}){const [occupied,setOccupied]=useState<string[]>([]);useEffect(()=>{let active=true;const refresh=()=>apiRequest<{code:string;status:string}[]>(`/api/v1/showtimes/${showtimeId}/seats`).then(items=>{if(active)setOccupied(items.filter(item=>item.status!=='available'&&!selected.includes(item.code)).map(item=>item.code))}).catch(()=>{});refresh();const timer=window.setInterval(refresh,3000);return()=>{active=false;clearInterval(timer)}},[showtimeId,selected]);return <><div className="page-title"><span className="eyebrow">ETAPA 1 DE 5</span><h1>Escolha seus assentos</h1><p>{busy?'Reservando assento...':'Toque nos lugares que deseja reservar.'}</p></div><div className="screen"><span>TELA</span></div><div className="seat-map">{['A','B','C','D','E','F','G','H'].map(row=><div className="seat-row" key={row}><b>{row}</b>{Array.from({length:10},(_,i)=>{const id=row+(i+1),occ=occupied.includes(id),special=(row==='H'&&(i===0||i===9));return <button aria-label={`Assento ${id}`} disabled={occ||busy} className={`seat ${selected.includes(id)?'chosen':''} ${occ?'occupied':''} ${special?'special':''}`} onClick={()=>onToggle(id)} key={id}>{special?'♿':i+1}</button>})}<b>{row}</b></div>)}</div><div className="legend"><span><i className="seat"/>Disponível</span><span><i className="seat chosen"/>Selecionado</span><span><i className="seat occupied"/>Ocupado</span><span><i className="seat special">♿</i>Acessível</span></div><Nav back={onBack} next={onNext} nextText="Continuar" disabled={!selected.length||busy}/></>}

function Tickets({ticketTypes,counts,setCounts,seats,onBack,onNext}:{ticketTypes:TicketType[];counts:Counts;setCounts:(c:Counts)=>void;seats:number;onBack:()=>void;onNext:()=>void}){const chosen=Object.values(counts).reduce((a,b)=>a+b,0);return <><div className="page-title"><span className="eyebrow">ETAPA 2 DE 5</span><h1>Escolha os ingressos</h1><p>Você selecionou {seats} {seats===1?'assento':'assentos'}. Atribua um ingresso para cada lugar.</p></div><div className="progress-card"><span>Ingressos selecionados</span><b>{chosen} de {seats}</b><div><i style={{width:`${Math.min(100,chosen/seats*100)}%`}}/></div></div><div className="ticket-list">{ticketTypes.map(t=><article key={t.id}><div className="ticket-icon">🎟</div><div><h3>{t.name}</h3><p>{t.detail}</p></div><strong>{money(t.price)}</strong><Counter value={counts[t.id]||0} max={seats} onChange={v=>setCounts({...counts,[t.id]:v})}/></article>)}</div><div className="notice">ⓘ Ingressos de meia-entrada exigem documento comprobatório na entrada da sala.</div><Nav back={onBack} next={onNext} nextText="Ir para Pipoca"/></>}

function Food({products,cart,setCart,onBack,onNext}:{products:Product[];cart:Counts;setCart:(c:Counts)=>void;onBack:()=>void;onNext:()=>void}){const [cat,setCat]=useState('Destaques');const visible=cat==='Destaques'?products:products.filter(p=>p.category===cat);return <><div className="page-title"><span className="eyebrow">ETAPA 3 DE 5</span><h1>Deixe seu filme mais gostoso</h1><p>Escolha seus favoritos e retire no balcão.</p></div><div className="category-tabs">{['Destaques','Combos','Pipocas','Bebidas','Doces'].map(c=><button className={cat===c?'selected':''} onClick={()=>setCat(c)} key={c}>{c}</button>)}</div><div className="product-grid">{visible.map(p=><article className="product" key={p.id}><div className="product-pic">{p.icon}</div><div><small>{p.category}</small><h3>{p.name}</h3><p>{p.description}</p><strong>{money(p.price)}</strong></div><Counter value={cart[p.id]||0} onChange={v=>setCart({...cart,[p.id]:v})}/></article>)}</div><Nav back={onBack} next={onNext} nextText={Object.values(cart).some(Boolean)?'Continuar':'Pular esta etapa'}/></>}

function Identify({onBack,onNext}:{onBack:()=>void;onNext:(customer:{kind:'cpf'|'email';value:string})=>void}){
 const [mode,setMode]=useState<'cpf'|'email'>('cpf'),[value,setValue]=useState('')
 const valid=mode==='cpf'?isValidCpf(value):isValidGmail(value)
 const canContinue=mode==='cpf'?isValidCpf(value):value.toLowerCase().endsWith('@gmail.com')&&isValidGmail(value)
 const complete=mode==='cpf'?value.length===11:value.includes('@')
 const key=(k:string)=>setValue(current=>{
   if(k==='⌫') return current.slice(0,-1)
   const char=k.toLowerCase()
   if(mode==='cpf') return /^\d$/.test(char)&&current.length<11?current+char:current
   if(current.length>=73 || (char==='@'&&current.includes('@')) || (char==='.'&&(current.endsWith('.')||current.endsWith('@'))) || !/^[a-z0-9@.]$/.test(char)) return current
   return current+char
 })
 const changeMode=(next:'cpf'|'email')=>{setMode(next);setValue('')}
 const continueSafely=()=>{if(canContinue) onNext({kind:mode,value})}
 return <><div className="page-title"><span className="eyebrow">IDENTIFICAÇÃO</span><h1>Como podemos identificar você?</h1><p>Enviaremos seus ingressos e o comprovante da compra.</p></div><div className="identify-card"><div className="switch"><button className={mode==='cpf'?'selected':''} onClick={()=>changeMode('cpf')}>CPF</button><button className={mode==='email'?'selected':''} onClick={()=>changeMode('email')}>E-mail</button></div><label>{mode==='cpf'?'Digite seu CPF':'Digite seu e-mail Gmail'}<div className={`fake-input ${complete&&!valid?'invalid':valid?'valid':''}`}>{value?(mode==='cpf'?formatCpf(value):value):<span>{mode==='cpf'?'000.000.000-00':'voce@gmail.com'}</span>}<i>|</i></div></label>{mode==='email'&&<button className="gmail-shortcut" onClick={()=>setValue(current=>{const local=current.split('@')[0].replace(/\.+$/,'');return local?`${local}@gmail.com`:current})}>Adicionar @gmail.com</button>}<p className={`field-help ${complete&&!valid?'error':valid?'success-text':''}`}>{valid?'✓ Dados válidos':mode==='cpf'?(complete?'CPF inválido. Confira os números digitados.':'O CPF deve conter 11 dígitos válidos.'):(complete?'Use um endereço válido terminado em @gmail.com.':'Digite o usuário e complete com @gmail.com.')}</p><VirtualKeyboard numeric={mode==='cpf'} onKey={key}/><p className="privacy">🔒 Seus dados estão seguros e serão usados apenas nesta compra.</p></div><Nav back={onBack} next={continueSafely} nextText="Continuar" disabled={!canContinue}/></>
}

function Payment({total,busy,onBack,onNext}:{total:number;busy:boolean;onBack:()=>void;onNext:(method:string)=>void}){const [method,setMethod]=useState('');return <><div className="page-title"><span className="eyebrow">ETAPA 4 DE 5</span><h1>Como deseja pagar?</h1><p>{busy?'Processando pagamento...':'Escolha uma opção e siga as instruções da maquininha.'}</p></div><div className="payment-list">{[['credit','Crédito','Até 3x sem juros','▣'],['debit','Débito','Pagamento à vista','▤'],['pix','PIX','Aprovação imediata','◆']].map(m=><button disabled={busy} className={method===m[0]?'selected':''} onClick={()=>setMethod(m[0])} key={m[0]}><i>{m[3]}</i><span><b>{m[1]}</b><small>{m[2]}</small></span><em>{method===m[0]?'✓':'›'}</em></button>)}</div><div className="pay-total"><span>Total a pagar</span><b>{money(total)}</b></div><Nav back={onBack} next={()=>onNext(method)} nextText={busy?'Processando...':'Pagar agora'} disabled={!method||busy}/></>}

function Success({movie,date,time,seats,total,reset}:{movie:Movie;date:string;time:string;seats:string[];total:number;reset:()=>void}){const formatted=new Date(`${date}T12:00:00`).toLocaleDateString('pt-BR',{day:'2-digit',month:'short',year:'numeric'}).toUpperCase();return <main className="success"><div className="success-check">✓</div><span className="eyebrow">COMPRA APROVADA</span><h1>Pronto, é só curtir o filme!</h1><p>Seus ingressos foram emitidos com sucesso.</p><div className="ticket-receipt"><Poster movie={movie}/><div><small>FILME</small><h2>{movie.title}</h2><div className="receipt-grid"><span><small>DATA</small><b>{formatted}</b></span><span><small>HORÁRIO</small><b>{time}</b></span><span><small>SALA</small><b>04</b></span><span><small>ASSENTOS</small><b>{seats.join(', ')}</b></span></div></div><div className="qr">▦<small>Leia o QR code</small></div></div><div className="success-total">Total pago <b>{money(total)}</b></div><p className="print">Seu comprovante está sendo impresso abaixo.</p><button className="primary" onClick={reset}>Finalizar e voltar ao início</button></main>}

function Nav({back,next,nextText,disabled=false}:{back:()=>void;next:()=>void;nextText:string;disabled?:boolean}){return <div className="nav"><button className="secondary" onClick={back}>← Voltar</button><button className="primary" disabled={disabled} onClick={next}>{nextText} →</button></div>}
export default App
