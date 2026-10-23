'use strict';

// Интерфейс без сборщика. Данные живут в API/БД; localStorage не хранит сессию.
const $ = (selector, root = document) => root.querySelector(selector);
const S = {user:null, csrf:'', students:[], lessons:[], homework:[], page:'overview', authMode:'login', day:today(), week:weekStart(today()), filter:'all', search:''};
const paths = {
  grid:'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',
  users:'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2 M17 4a4 4 0 0 1 0 8 M22 21v-2a4 4 0 0 0-3-3.87 M13 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0',
  calendar:'M8 2v4 M16 2v4 M3 10h18 M5 4h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2 M7 14h3 M14 14h3 M7 18h3',
  book:'M4 3h12l4 4v14H4z M15 3v5h5 M8 12h8 M8 16h5',
  plus:'M12 5v14 M5 12h14', arrow:'M5 12h14 M13 6l6 6-6 6', chevron:'M9 5l7 7-7 7', left:'M15 5l-7 7 7 7',
  check:'M5 12l4 4L19 6', clock:'M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0 M12 6v6l4 2',
  search:'M21 21l-5-5 M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0', close:'M6 6l12 12 M6 18L18 6',
  logout:'M9 4H4v16h5 M10 12h11 M17 8l4 4-4 4', edit:'M16 3l5 5-12 12-6 1 1-6z M13 6l5 5',
  settings:'M12 8a4 4 0 1 1 0 8 4 4 0 0 1 0-8 M9 3h6l1 3 3 1 2 5-2 5-3 1-1 3H9l-1-3-3-1-2-5 2-5 3-1z',
  leaf:'M20 3C9 1 2 6 4 14s14 8 16-11 M4 21L16 9', chart:'M4 20V10 M10 20V4 M16 20v-7 M22 20H2', money:'M4 5h16v14H4z M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0'
};
const icon = name => `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${paths[name] || paths.book}"/></svg>`;
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const initials = name => name.split(/\s+/).slice(0,2).map(x=>x[0]).join('').toUpperCase();
const avatar = (name, n=0) => `<div class="avatar c${n%4}">${esc(initials(name))}</div>`;
const teacher = () => S.user?.role === 'teacher';
const money = n => new Intl.NumberFormat('ru-RU').format(n) + ' ₽';
const dateFmt = (value, opts={}) => new Intl.DateTimeFormat('ru-RU',{timeZone:'Europe/Moscow', ...opts}).format(new Date(value));
const timeFmt = value => dateFmt(value,{hour:'2-digit',minute:'2-digit'});
const shortDate = value => dateFmt(value,{day:'numeric',month:'short'});
function keyOf(value){return new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Moscow',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(value));}
function today(){return keyOf(new Date());}
function addDays(key,n){const d = new Date(key+'T12:00:00Z'); d.setUTCDate(d.getUTCDate()+n); return d.toISOString().slice(0,10);}
function weekStart(key){const day = new Date(key+'T12:00:00Z').getUTCDay();return addDays(key,-((day+6)%7));}
function localInput(value){return keyOf(value)+'T'+timeFmt(value);}
function fromInput(value){return new Date(value+':00+03:00').toISOString();}
function label(status){return ({scheduled:'Запланировано',completed:'Проведено',cancelled:'Отменено',assigned:'К выполнению',submitted:'На проверке',reviewed:'Проверено'})[status] || status;}
function badge(status){const color = ({scheduled:'blue',completed:'',cancelled:'gray',assigned:'amber',submitted:'blue',reviewed:''})[status];return `<span class="pill ${color || ''}">${label(status)}</span>`;}
const button = (action,text,style='',id='',symbol='') => `<button type="button" class="btn ${style}" data-action="${action}" ${id!==''?`data-id="${id}"`:''}>${symbol?icon(symbol):''}${text}</button>`;
const average = id => {const scores=S.homework.filter(h=>h.grade!==null && (!id||h.student_id===id)).map(h=>h.grade); return scores.length?Math.round(scores.reduce((a,b)=>a+b,0)/scores.length):null;};
function toast(message,error=false){const node=$('#toast');node.textContent=message;node.className='visible'+(error?' error':'');clearTimeout(toast.timer);toast.timer=setTimeout(()=>node.className='',4000);}
async function api(url,method='GET',data){
  const headers = {};
  if(data!==undefined) headers['Content-Type']='application/json';
  if(S.csrf) headers['X-CSRF-Token']=S.csrf;
  const response=await fetch('/api'+url,{method,headers,credentials:'same-origin',body:data===undefined?undefined:JSON.stringify(data)});
  const payload=response.status===204?null:await response.json();
  if(!response.ok){
    const error=new Error(payload?.detail || 'Не удалось выполнить запрос');error.status=response.status;
    if(payload?.errors)error.message += ': '+payload.errors.map(e=>e.field+' — '+e.message).join('; ');
    if(response.status===401 && S.user){S.user=null;S.csrf='';$('#modal').close();renderAuth();}
    throw error;
  }
  return payload;
}
async function refresh(){[S.students,S.lessons,S.homework]=await Promise.all([api('/students'),api('/lessons'),api('/homework')]);render();}
async function boot(){try{const data=await api('/auth/me');S.user=data.user;S.csrf=data.csrf_token;await refresh();}catch(error){if(error.status===401)renderAuth();else $('#root').innerHTML=`<div class="empty">Не удалось загрузить кабинет. Проверьте, запущен ли сервер.<br>${button('reload','Повторить','secondary')}</div>`;}}

function renderAuth(){
  const reg=S.authMode==='register';
  $('#root').innerHTML=`<div class="auth-layout"><aside class="auth-story"><div class="brand"><span class="brand-mark">T</span>TutorDesk</div><div class="auth-copy"><div class="eyebrow">Ваше пространство для преподавания</div><h1>Занятия и задания<br>в одном кабинете.</h1><p>Планируйте уроки, отправляйте задания и проверяйте ответы учеников.</p><div class="auth-note">${icon('leaf')}<div><strong>Первый раз здесь?</strong><p>Создайте кабинет преподавателя. Ученикам вы сможете выдать отдельный доступ.</p></div></div></div><div class="auth-story-footer">TutorDesk · кабинет репетитора</div></aside><main class="auth-form-side"><div class="auth-box"><div class="eyebrow subtle">Добро пожаловать</div><h2>${reg?'Ваш новый рабочий стол':'Рады видеть вас снова'}</h2><p class="subtle">${reg?'Создайте аккаунт репетитора и добавьте первого ученика.':'Войдите, чтобы продолжить с того места, где остановились.'}</p><div class="tabs"><button data-action="auth-login" class="${!reg?'active':''}">Войти</button><button data-action="auth-register" class="${reg?'active':''}">Я новый репетитор</button></div><form id="auth-form">${reg?field('name','Ваше имя','text','','Например, Тарас','required maxlength="100" autocomplete="name"'):''}${field('email','Email','email','','name@example.com','required maxlength="254" autocomplete="username"')}${field('password','Пароль','password','','Не менее 8 символов',`required minlength="8" maxlength="128" autocomplete="${reg?'new-password':'current-password'}"`)}<div class="form-error" role="alert"></div><button class="btn" type="submit">${reg?'Создать кабинет':'Войти в кабинет'} ${icon('arrow')}</button></form><p class="auth-bottom">Ученикам аккаунт создаёт преподаватель.<br>Используйте email и пароль, которые он вам передал.</p></div></main></div>`;
}
function render(){
  if(!S.user)return renderAuth();
  const pageNames={overview:'Обзор',students:teacher()?'Ученики':'Мой профиль',schedule:'Расписание',homework:'Домашние задания',settings:'Настройки'};
  const nav=[['overview','grid',pageNames.overview],['students','users',pageNames.students],['schedule','calendar',pageNames.schedule],['homework','book','Задания'],['settings','settings','Настройки']];
  const pending=S.homework.filter(h=>h.status===(teacher()?'submitted':'assigned')).length;
  $('#root').innerHTML=`<div class="layout"><aside class="sidebar"><div class="brand"><span class="brand-mark">T</span>TutorDesk</div><div class="workspace-label eyebrow">Рабочее пространство</div><nav class="nav" aria-label="Главное меню">${nav.map(([id,ico,title])=>`<button data-action="nav" data-id="${id}" class="${S.page===id?'active':''}" ${S.page===id?'aria-current="page"':''}>${icon(ico)}${title}${id==='homework'&&pending?`<span class="count">${pending}</span>`:''}</button>`).join('')}</nav><div class="sidebar-bottom"><div class="sidebar-note">${icon('leaf')}<p>Время занятий<br>указано по Москве.</p></div><div class="account">${avatar(S.user.name)}<div class="account-info"><strong>${esc(S.user.name)}</strong><span>${teacher()?'Репетитор':'Ученик'}</span></div><button class="icon-btn" data-action="logout" aria-label="Выйти из аккаунта" title="Выйти">${icon('logout')}</button></div></div></aside><main class="main"><header class="topbar"><div class="breadcrumb">Мой кабинет <strong>/ ${pageNames[S.page]}</strong></div><div class="topbar-right"><span class="status-text"><i class="live-dot"></i>Всё под рукой</span><span>Москва · UTC+3</span><button class="icon-btn" data-action="nav" data-id="settings" aria-label="Настройки профиля">${icon('settings')}</button></div></header><div id="page">${({overview:overview,students:studentsPage,schedule:schedulePage,homework:homeworkPage,settings:settingsPage})[S.page]()}</div><footer class="footer"><span>TutorDesk · кабинет репетитора</span><span>Версия 0.2 · ${dateFmt(new Date(),{day:'numeric',month:'long',year:'numeric'})}</span></footer></main></div>`;
}
function heading(title,description,actions=''){return `<div class="page-heading"><div><h1>${title}</h1><p class="subtle">${description}</p></div><div class="heading-actions">${actions}</div></div>`;}
function stat(title,value,note,ico){return `<article class="stat"><div class="stat-head">${title}${icon(ico)}</div><div class="stat-value">${value}</div><div class="stat-foot">${note}</div></article>`;}
function empty(text,action='',btnText=''){return `<div class="empty">${icon('leaf')}${text}${action?'<br>'+button(action,btnText,'secondary small'):''}</div>`;}
function weekStrip(){return `<div class="week-strip">${Array.from({length:7},(_,i)=>{const key=addDays(S.week,i);const has=S.lessons.some(l=>keyOf(l.starts_at)===key&&l.status!=='cancelled');return `<button class="day ${key===S.day?'active':''} ${has?'has-lessons':''}" data-action="day" data-id="${key}" aria-label="${dateFmt(key+'T12:00:00Z',{day:'numeric',month:'long'})}"><span>${dateFmt(key+'T12:00:00Z',{weekday:'short'})}</span><b>${Number(key.slice(-2))}</b><i></i></button>`;}).join('')}</div>`;}
function lessonRow(l,i=0){return `<div class="lesson-row"><div class="lesson-time">${timeFmt(l.starts_at)}<small>${timeFmt(l.ends_at)}</small></div><div class="lesson-accent c${i%3}"></div><div class="lesson-info"><h3>${esc(l.title)}</h3><p>${esc(teacher()?l.student_name:l.subject)} · ${l.duration_minutes} мин</p></div>${badge(l.status)}<button class="icon-btn" data-action="${teacher()?'lesson-edit':'lesson-view'}" data-id="${l.id}" aria-label="Открыть занятие ${esc(l.title)}">${icon('chevron')}</button></div>`;}
function overview(){
  const date=today(), end=addDays(date,7), month=date.slice(0,7);
  const upcoming=S.lessons.filter(l=>l.status==='scheduled'&&keyOf(l.starts_at)>=date&&keyOf(l.starts_at)<end);
  const complete=S.lessons.filter(l=>l.status==='completed'&&keyOf(l.starts_at).slice(0,7)===month);
  const pending=S.homework.filter(h=>h.status===(teacher()?'submitted':'assigned'));
  const dayLessons=S.lessons.filter(l=>keyOf(l.starts_at)===S.day&&l.status!=='cancelled');
  const firstName=esc(S.user.name.split(' ')[0]);
  const active=S.students.filter(s=>!s.archived);
  const summary=teacher()?stat('Активных учеников',active.length,'Каждый со своей целью','users')+stat('Занятий за 7 дней',upcoming.length,'Сегодня и ближайшая неделя','calendar')+stat('Заданий на проверке',pending.length,'Ждут вашей обратной связи','book')+stat('Проведено за месяц',money(complete.reduce((a,l)=>a+l.price,0)),'Стоимость занятий, не учёт оплат','money'):stat('Занятий за 7 дней',upcoming.length,'Ваше ближайшее расписание','calendar')+stat('Заданий к выполнению',pending.length,'Двигайтесь в своём темпе','book')+stat('Средний результат',average()??'—','Баллы за проверенные задания','chart')+stat('Занятий за месяц',complete.length,'Уже пройденный путь','check');
  return heading(`Добрый день, ${firstName}`, 'Ближайшие занятия и задания, которые требуют внимания.',teacher()?button('lesson-new','Новое занятие','','','plus'):'')+`<section class="welcome"><div><div class="eyebrow">${dateFmt(new Date(),{weekday:'long',day:'numeric',month:'long'})}</div><h2>${teacher()?'Что на сегодня?':'Ваши занятия<br>и домашние задания.'}</h2><p class="subtle">${teacher()?'Расписание собрано, задания под рукой. Можно сосредоточиться на главном.':'Смотрите ближайшие занятия, выполняйте задания и замечайте свой прогресс.'}</p></div><div class="welcome-art" aria-hidden="true"><div class="art-page"><i></i><i></i><i></i><i></i></div><div class="art-circle">${icon('check')}</div><div class="art-star">✧</div></div></section><section class="stats">${summary}</section><div class="dashboard-grid"><section class="panel"><div class="panel-head"><div><h2>План на неделю</h2><p class="subtle">${shortDate(S.week+'T12:00:00Z')} — ${shortDate(addDays(S.week,6)+'T12:00:00Z')}</p></div><button class="text-btn" data-action="nav" data-id="schedule">Всё расписание ${icon('arrow')}</button></div>${weekStrip()}${dayLessons.length?dayLessons.map(lessonRow).join(''):empty('На этот день занятий нет.<br>Можно запланировать что-то хорошее.',teacher()?'lesson-new':'', 'Добавить занятие')}</section><section class="panel"><div class="panel-head"><div><h2>${teacher()?'Ждут проверки':'Ваши задания'}</h2><p class="subtle">${teacher()?'Обратная связь помогает двигаться дальше':'Каждое выполненное задание — шаг вперёд'}</p></div><span class="pill">${pending.length}</span></div>${pending.length?pending.slice(0,3).map(h=>`<div class="hw-row"><div class="hw-icon">${icon('book')}</div><div class="info"><h3>${esc(h.title)}</h3><p>${esc(h.student_name)} · до ${shortDate(h.due_at)}</p>${badge(h.status)}</div><button class="icon-btn" data-action="homework-open" data-id="${h.id}" aria-label="Открыть задание">${icon('chevron')}</button></div>`).join(''):empty(teacher()?'Все ответы проверены.<br>Можно выдохнуть.':'Пока нет новых заданий.')}<div style="padding:8px 17px 14px"><button class="text-btn" data-action="nav" data-id="homework">Все задания ${icon('arrow')}</button></div></section></div>${teacher()?`<section class="panel students-preview"><div class="panel-head"><div><h2>Ваши ученики</h2><p class="subtle">Предметы, результаты и ближайшие занятия.</p></div><button class="text-btn" data-action="nav" data-id="students">Все ученики ${icon('arrow')}</button></div>${active.length?`<div class="table-wrap"><table><thead><tr><th>Ученик</th><th>Предмет</th><th>Результат ДЗ</th><th>Ближайшее занятие</th><th></th></tr></thead><tbody>${active.slice(0,4).map((s,i)=>{const avg=average(s.id);const next=S.lessons.find(l=>l.student_id===s.id&&l.status==='scheduled'&&new Date(l.starts_at)>=new Date());return `<tr><td><div class="person-cell">${avatar(s.name,i)}<div>${esc(s.name)}<div class="subtle">${esc(s.level)}</div></div></td><td><span class="pill ${s.subject.includes('Информатика')?'blue':''}">${esc(s.subject)}</span></td><td>${avg!==null?`${avg} / 100<div class="progress"><span style="width:${avg}%"></span></div>`:'Нет оценок'}</td><td class="nowrap">${next?shortDate(next.starts_at)+', '+timeFmt(next.starts_at):'Не назначено'}</td><td><button class="icon-btn" data-action="student-edit" data-id="${s.id}" aria-label="Карточка ученика">${icon('chevron')}</button></td></tr>`;}).join('')}</tbody></table></div>`:empty('Добавьте первого ученика — здесь начнётся ваша история.','student-new','Добавить ученика')}</section>`:''}`;
}
function studentCard(s,i){const avg=average(s.id);return `<article class="student-card"><div class="student-card-top">${avatar(s.name,i)}<span class="pill ${s.archived?'gray':'blue'}">${s.archived?'В архиве':esc(s.subject)}</span></div><h3>${esc(s.name)}</h3><p class="subtle">${esc(s.level||s.email)}</p><div class="student-goal">${esc(s.goal||'Цель пока не указана')}<br><span class="subtle">Средний результат ДЗ: ${avg===null?'пока нет оценок':avg+' / 100'}</span></div>${teacher()?`<div class="student-actions">${button('student-edit','Карточка','secondary small',s.id)}${!s.archived?button('lesson-new','Занятие','small',s.id):''}</div>`:`<p class="subtle">${esc(s.email)}</p>`}</article>`;}
function studentsPage(){const visible=S.students.filter(s=>(!teacher()||(S.filter==='archived'?s.archived:!s.archived))&&`${s.name} ${s.subject} ${s.level}`.toLowerCase().includes(S.search.toLowerCase()));return heading(teacher()?'Ученики':'Мой профиль',teacher()?'У каждого ученика — своя цель. Помогите к ней прийти.':'Ваша цель и результаты занятий.',teacher()?button('student-new','Добавить ученика','','','plus'):'')+(teacher()?`<div class="toolbar"><div class="search">${icon('search')}<input id="student-search" aria-label="Поиск учеников" placeholder="Найти ученика или предмет…" value="${esc(S.search)}"></div><div class="tabs"><button data-action="filter" data-id="all" class="${S.filter!=='archived'?'active':''}">Активные</button><button data-action="filter" data-id="archived" class="${S.filter==='archived'?'active':''}">Архив</button></div></div>`:'')+`<div class="student-grid" id="student-list">${visible.map(studentCard).join('')}</div>${visible.length?'':empty('Здесь пока никого нет.',teacher()&&S.filter!=='archived'?'student-new':'','Добавить первого ученика')}`;}
function schedulePage(){const list=S.lessons.filter(l=>keyOf(l.starts_at)===S.day);return heading('Расписание','Ритм занятий, в котором есть место для всего.',teacher()?button('lesson-new','Новое занятие','','','plus'):'')+`<div class="toolbar"><div class="calendar-nav"><button class="icon-btn" data-action="week-prev" aria-label="Предыдущая неделя">${icon('left')}</button><strong>${shortDate(S.week+'T12:00:00Z')} — ${shortDate(addDays(S.week,6)+'T12:00:00Z')}, ${S.week.slice(0,4)}</strong><button class="icon-btn" data-action="week-next" aria-label="Следующая неделя">${icon('chevron')}</button></div>${button('today','Сегодня','secondary small')}</div><section class="panel schedule-panel">${weekStrip()}<div class="date-heading">${dateFmt(S.day+'T12:00:00Z',{weekday:'long',day:'numeric',month:'long'})}</div>${list.length?list.map(lessonRow).join(''):empty('Свободный день. Добавьте занятие или оставьте время для себя.',teacher()?'lesson-new':'','Добавить занятие')}</section>`;}
function homeworkPage(){const list=S.homework.filter(h=>S.filter==='all'||h.status===S.filter);return heading('Домашние задания',teacher()?'Выданные задания, ответы учеников и результаты проверки.':'Практикуйтесь, отправляйте решения и получайте обратную связь.',teacher()?button('homework-new','Выдать задание','','','plus'):'')+`<div class="toolbar"><div class="tabs">${[['all','Все'],['assigned','К выполнению'],['submitted','На проверке'],['reviewed','Проверено']].map(([id,text])=>`<button data-action="filter" data-id="${id}" class="${S.filter===id?'active':''}">${text}</button>`).join('')}</div><span class="subtle">Всего: ${list.length}</span></div><div class="homework-grid">${list.map(h=>`<article class="homework-card"><div class="homework-top">${badge(h.status)}<span class="subtle ${new Date(h.due_at)<new Date()&&h.status==='assigned'?'overdue':''}">${new Date(h.due_at)<new Date()&&h.status==='assigned'?'Срок прошёл · ':''}до ${shortDate(h.due_at)}</span></div><h3>${esc(h.title)}</h3><p>${esc(h.description.slice(0,180))}${h.description.length>180?'…':''}</p><div class="card-footer"><div class="person-cell">${avatar(h.student_name,h.student_id)}<span>${esc(h.student_name)}</span></div>${button('homework-open',h.status==='reviewed'?h.grade+' / 100':teacher()&&h.status==='submitted'?'Проверить':'Открыть','secondary small',h.id)}</div></article>`).join('')}</div>${list.length?'':empty('Заданий в этом разделе пока нет.',teacher()?'homework-new':'','Выдать задание')}`;}
function settingsPage(){return heading('Настройки','Ваш аккаунт и безопасность.')+`<section class="panel settings-card"><h3>${esc(S.user.name)}</h3><p class="subtle">${esc(S.user.email)} · ${teacher()?'Репетитор':'Ученик'}</p><div class="muted-block">Время занятий и сроков в приложении отображается по Москве (UTC+3).</div><h3>Сменить пароль</h3><form id="password-form">${field('current_password','Текущий пароль','password','','','required minlength="8" maxlength="128" autocomplete="current-password"')}${field('new_password','Новый пароль','password','','Не менее 8 символов','required minlength="8" maxlength="128" autocomplete="new-password"')}<div class="form-error" role="alert"></div><button class="btn" type="submit">Сменить пароль</button><p class="subtle" style="margin-top:12px">После смены пароля потребуется войти снова.</p></form><div class="modal-actions">${button('logout','Выйти из аккаунта','secondary','','logout')}</div></section>`;}

function field(name,labelText,type='text',value='',placeholder='',attrs=''){return `<div class="field"><label for="f-${name}">${labelText}</label><input id="f-${name}" name="${name}" type="${type}" value="${esc(value)}" placeholder="${esc(placeholder)}" ${attrs}></div>`;}
function textarea(name,labelText,value='',attrs=''){return `<div class="field"><label for="f-${name}">${labelText}</label><textarea id="f-${name}" name="${name}" ${attrs}>${esc(value)}</textarea></div>`;}
function select(name,labelText,options){return `<div class="field"><label for="f-${name}">${labelText}</label><select id="f-${name}" name="${name}">${options}</select></div>`;}
function studentOptions(selected){return S.students.filter(s=>!s.archived||s.id===Number(selected)).map(s=>`<option value="${s.id}" ${s.id===Number(selected)?'selected':''}>${esc(s.name)}</option>`).join('');}
function showModal(title,subtitle,body){$('#modal-content').innerHTML=`<div class="modal-head"><div><h2>${title}</h2><p>${subtitle}</p></div><button class="icon-btn" data-action="close" aria-label="Закрыть">${icon('close')}</button></div><div class="modal-body">${body}</div>`;$('#modal').showModal();}
function formActions(text='Сохранить'){return `<div class="form-error" role="alert"></div><div class="modal-actions">${button('close','Отмена','secondary')}<button class="btn" type="submit">${text} ${icon('check')}</button></div>`;}
function studentModal(id){const s=S.students.find(s=>s.id===Number(id));showModal(s?'Карточка ученика':'Новый ученик',s?'Цель, детали и личные заметки':'Создадим карточку и доступ в личный кабинет',`<form id="student-form" data-id="${s?.id||''}">${field('name','Имя и фамилия','text',s?.name||'','','required maxlength="100"')}${!s?`<div class="form-row">${field('email','Email ученика','email','','name@example.com','required maxlength="254" autocomplete="off"')}${field('password','Первый пароль','password','','Не менее 8 символов','required minlength="8" maxlength="128" autocomplete="new-password"')}</div><div class="muted-block">Передайте ученику email и пароль лично. Он сможет изменить пароль в настройках. Автоматическая отправка писем пока не подключена.</div>`:`<p class="muted-block">Email для входа: ${esc(s.email)}</p>`}<div class="form-row">${field('subject','Предмет','text',s?.subject||'Математика','','required maxlength="100"')}${field('level','Класс / направление','text',s?.level||'','11 класс · ЕГЭ','maxlength="100"')}</div>${field('goal','Цель обучения','text',s?.goal||'','Например, 85+ баллов на ЕГЭ','maxlength="300"')}${field('contact','Контакт для связи','text',s?.contact||'','Телефон или Telegram','maxlength="200"')}${textarea('notes','Ваши личные заметки',s?.notes||'','maxlength="5000"')}${s?`<label class="checkline"><input type="checkbox" name="archived" ${s.archived?'checked':''}>Ученик в архиве</label><p class="subtle">Архив сохраняет историю. Назначенные занятия и доступ ученика сохраняются.</p>`:''}${formActions(s?'Сохранить':'Добавить ученика')}</form>`);}
function lessonModal(id,studentId){
  const l=S.lessons.find(l=>l.id===Number(id));
  if(!S.students.some(s=>!s.archived)&&!l){toast('Сначала добавьте ученика');studentModal();return;}
  showModal(l?'Занятие':'Новое занятие','Дата и время — по Москве (UTC+3)',`<form id="lesson-form" data-id="${l?.id||''}">${select('student_id','Ученик',studentOptions(l?.student_id||studentId))}${field('title','Тема занятия','text',l?.title||'','','required maxlength="200"')}<div class="form-row">${field('starts_at','Дата и время','datetime-local',l?localInput(l.starts_at):S.day+'T15:00','','required')}${field('duration_minutes','Длительность, минут','number',l?.duration_minutes||60,'','required min="15" max="240"')}</div><div class="form-row">${field('price','Стоимость, ₽','number',l?.price??1800,'','required min="0" max="100000"')}${select('status','Статус',['scheduled','completed','cancelled'].map(v=>`<option value="${v}" ${l?.status===v?'selected':''}>${label(v)}</option>`).join(''))}</div>${textarea('notes','Личные заметки преподавателя',l?.notes||'','maxlength="5000"')}${formActions()}</form>`);
}
function lessonView(id){const l=S.lessons.find(l=>l.id===Number(id));if(!l)return;showModal('Ваше занятие',shortDate(l.starts_at)+', '+timeFmt(l.starts_at)+'–'+timeFmt(l.ends_at)+' · Москва',`<h3>${esc(l.title)}</h3><div class="detail-text">${esc(l.subject)}<br>Длительность: ${l.duration_minutes} минут<br>Стоимость: ${money(l.price)}</div>${badge(l.status)}<div class="modal-actions">${button('close','Понятно')}</div>`);}
function lessonOptions(studentId){return '<option value="">Без привязки к занятию</option>'+S.lessons.filter(l=>l.student_id===Number(studentId)).map(l=>`<option value="${l.id}">${esc(l.title)} · ${shortDate(l.starts_at)}</option>`).join('');}
function homeworkModal(){const active=S.students.filter(s=>!s.archived);if(!active.length){toast('Сначала добавьте ученика');studentModal();return;}showModal('Новое задание','Укажите условие и срок сдачи',`<form id="homework-form">${select('student_id','Ученик',studentOptions())}${select('lesson_id','Связанное занятие',lessonOptions(active[0].id))}${field('title','Название задания','text','','Например, производная и экстремумы','required maxlength="200"')}${textarea('description','Условие и рекомендации','','required maxlength="10000"')}${field('due_at','Срок сдачи · Москва','datetime-local',addDays(today(),2)+'T20:00','','required')}${formActions('Выдать задание')}</form>`);}
function homeworkEditModal(id){
  const h=S.homework.find(h=>h.id===Number(id));
  if(!h||!teacher()||h.status!=='assigned')return;
  showModal('Изменить задание',esc(h.student_name),`<form id="homework-edit-form" data-id="${h.id}"><p class="muted-block">Можно исправить условие и срок, пока ученик не отправил ответ. Ученик и связанное занятие останутся прежними.</p>${field('title','Название задания','text',h.title,'','required maxlength="200"')}${textarea('description','Условие и рекомендации',h.description,'required maxlength="10000"')}${field('due_at','Срок сдачи · Москва','datetime-local',localInput(h.due_at),'','required')}${formActions('Сохранить изменения')}</form>`);
}
function homeworkView(id){const h=S.homework.find(h=>h.id===Number(id));if(!h)return;let body=`${badge(h.status)}<h3 style="margin-top:17px">${esc(h.title)}</h3><div class="detail-text">${esc(h.description)}</div>`;
  if(h.answer)body+=`<div class="detail-label">Ответ ученика</div><div class="detail-text">${esc(h.answer)}</div>`;
  if(h.status==='reviewed')body+=`<div class="detail-label">Результат</div><div class="grade">${h.grade}<span class="subtle"> / 100</span></div><div class="detail-text">${esc(h.feedback||'Задание проверено.')}</div>`;
  if(teacher()&&h.status!=='assigned')body+=`<form id="review-form" data-id="${h.id}">${field('grade','Оценка от 0 до 100','number',h.grade??90,'','required min="0" max="100"')}${textarea('feedback','Обратная связь',h.feedback,'maxlength="5000"')}${formActions('Сохранить оценку')}</form>`;
  else if(!teacher()&&h.status!=='reviewed')body+=`<form id="submit-form" data-id="${h.id}">${textarea('answer',h.answer?'Обновить ответ':'Ваше решение',h.answer,'required maxlength="10000"')}${formActions(h.answer?'Обновить ответ':'Отправить на проверку')}</form>`;
  else body+=`<div class="modal-actions">${teacher()&&h.status==='assigned'?button('homework-edit','Изменить задание','',h.id):''}${button('close','Закрыть','secondary')}</div>`;
  showModal('Домашнее задание',esc(h.student_name)+' · до '+shortDate(h.due_at)+', '+timeFmt(h.due_at)+' (Москва)',body);
}

document.addEventListener('click',async event=>{
  const b=event.target.closest('[data-action]');if(!b)return;
  const action=b.dataset.action,id=b.dataset.id;
  try{
    if(action==='nav'){S.page=id;S.filter='all';S.search='';render();}
    else if(action==='auth-login'||action==='auth-register'){S.authMode=action==='auth-login'?'login':'register';renderAuth();}
    else if(action==='logout'){await api('/auth/logout','POST');S.user=null;S.csrf='';S.page='overview';renderAuth();}
    else if(action==='close')$('#modal').close();
    else if(action==='reload')await boot();
    else if(action==='student-new')studentModal();
    else if(action==='student-edit')studentModal(id);
    else if(action==='lesson-new')lessonModal(null,id);
    else if(action==='lesson-edit')lessonModal(id);
    else if(action==='lesson-view')lessonView(id);
    else if(action==='homework-new')homeworkModal();
    else if(action==='homework-open')homeworkView(id);
    else if(action==='homework-edit')homeworkEditModal(id);
    else if(action==='filter'){S.filter=id;render();}
    else if(action==='day'){S.day=id;render();}
    else if(action==='week-prev'||action==='week-next'){const diff=action==='week-prev'?-7:7;S.week=addDays(S.week,diff);S.day=addDays(S.day,diff);render();}
    else if(action==='today'){S.day=today();S.week=weekStart(S.day);render();}
  }catch(error){toast(error.message,true);}
});
document.addEventListener('input',event=>{
  if(event.target.id==='student-search'){
    const caret=event.target.selectionStart;S.search=event.target.value;
    $('#page').innerHTML=studentsPage();const search=$('#student-search');search.focus();search.setSelectionRange(caret,caret);
  }
});
document.addEventListener('change',event=>{if(event.target.name==='student_id'&&event.target.closest('#homework-form'))$('#f-lesson_id').innerHTML=lessonOptions(event.target.value);});
document.addEventListener('submit',async event=>{
  event.preventDefault();const form=event.target;const errorBox=$('.form-error',form);if(errorBox)errorBox.textContent='';
  const submit=$('button[type="submit"]',form);submit.disabled=true;
  const data=Object.fromEntries(new FormData(form));const id=form.dataset.id;
  let saved=false;
  try{
    if(form.id==='auth-form'){
      const result=await api('/auth/'+S.authMode,'POST',data);S.user=result.user;S.csrf=result.csrf_token;S.page='overview';S.day=today();S.week=weekStart(S.day);S.filter='all';
      await refresh();return;
    }
    if(form.id==='password-form'){
      await api('/auth/password','POST',data);S.user=null;S.csrf='';renderAuth();toast('Пароль изменён. Войдите снова.');return;
    }
    if(form.id==='student-form'){
      if(id)data.archived=!!form.elements.archived.checked;
      await api('/students'+(id?'/'+id:''),id?'PUT':'POST',data);
    }
    if(form.id==='lesson-form'){
      for(const key of ['student_id','duration_minutes','price'])data[key]=Number(data[key]);
      data.starts_at=fromInput(data.starts_at);await api('/lessons'+(id?'/'+id:''),id?'PUT':'POST',data);
    }
    if(form.id==='homework-form'){
      data.student_id=Number(data.student_id);data.lesson_id=data.lesson_id?Number(data.lesson_id):null;data.due_at=fromInput(data.due_at);await api('/homework','POST',data);
    }
    if(form.id==='submit-form')await api(`/homework/${id}/submit`,'POST',data);
    if(form.id==='homework-edit-form'){
      data.due_at=fromInput(data.due_at);
      await api(`/homework/${id}`,'PUT',data);
    }
    if(form.id==='review-form'){data.grade=Number(data.grade);await api(`/homework/${id}/review`,'POST',data);}
    saved=true;$('#modal').close();await refresh();toast('Готово. Изменения сохранены.');
  }catch(error){
    if(saved)toast('Изменения сохранены. Обновите страницу, чтобы загрузить их.',true);
    else if(errorBox&&document.contains(errorBox))errorBox.textContent=error.message;
    else toast(error.message,true);
  }finally{submit.disabled=false;}
});
$('#modal').addEventListener('click',event=>{if(event.target===$('#modal')){const rect=event.target.getBoundingClientRect();if(event.clientX<rect.left||event.clientX>rect.right||event.clientY<rect.top||event.clientY>rect.bottom)event.target.close();}});
boot();
