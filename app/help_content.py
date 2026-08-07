# -*- coding: utf-8 -*-
"""Contingut de l'ajuda interna per a coordinadors.

Cada idioma tindrà una llista de seccions amb preguntes i respostes.
Mentre no hi hagi traducció, es retorna el català."""

from __future__ import annotations


HELP: dict[str, list[dict]] = {
    "ca": [
        {
            "id": "primeres-passos",
            "title": "Primeres passes",
            "questions": [
                {
                    "q": "Com entro per primer cop?",
                    "a": "Escriu el codi de club i la contrasenya. Si t'has oblidat la clau, prem “He oblidat la contrasenya?”. Rebràs un enllaç al correu del club si l'hem configurat.",
                    "link": "/login",
                },
                {
                    "q": "Com canvio la contrasenya?",
                    "a": "Ves al menú del club (“Ajustos”) i posa una contrasenya nova de com a mínim 8 caràcters. Assegura't de recordar-la o de tenir un correu de recuperació.",
                    "link": "/season/{season_id}/club",
                },
                {
                    "q": "Puc canviar l'idioma?",
                    "a": "Sí. A dalt a la dreta trobaràs un selector amb tots els idiomes. El canvi afectarà tota l'aplicació.",
                },
            ],
        },
        {
            "id": "federacio",
            "title": "Importar federació",
            "questions": [
                {
                    "q": "Com busco els partits federatius?",
                    "a": "Ves a Importar, escriu el nom del teu club i tria la federació (RFEP o FECAPA) i la comunitat autònoma. AtempoSports buscarà les convocatòries disponibles.",
                    "link": "/season/{season_id}/fed",
                },
                {
                    "q": "I si no trobo el meu club?",
                    "a": "Pots afegir els equips i els partits manualment des de les seccions Equips i Partits. L'opció de cerca només cobreix Espanya i les seves comunitats autònomes actualment.",
                },
                {
                    "q": "Es veuen els canvis de la federació?",
                    "a": "Sí. Quan la federació canvia horaris, AtempoSports ho detecta i t'avisarà a la pàgina d'inici perquè revisis els canvis abans d'aplicar-los.",
                    "link": "/app",
                },
            ],
        },
        {
            "id": "pistes",
            "title": "Pistes i franges",
            "questions": [
                {
                    "q": "Com afegeixo una pista?",
                    "a": "Ves a Pistes i escriu el nom. Després defineix les franges horàries disponibles (per exemple, els dilluns de 18:00 a 20:00).",
                    "link": "/season/{season_id}/venues",
                },
                {
                    "q": "Què és una franja?",
                    "a": "Una franja és un horari en què la pista està lliure per entrenar o jugar. Pots tenir diverses franges per dia i per pista.",
                },
                {
                    "q": "Puc bloquejar una franja?",
                    "a": "Si una franja no està disponible per a entrenaments, pots marcar-la o eliminar-la. Només les franges actives s'usen per generar propostes.",
                },
            ],
        },
        {
            "id": "equips",
            "title": "Equips i persones",
            "questions": [
                {
                    "q": "Com creo un equip?",
                    "a": "Ves a Equips i prem “Crear equip”. Pots escriure el nom manualment o enganxar una llista de noms si en tens molts.",
                    "link": "/season/{season_id}/teams",
                },
                {
                    "q": "Què són les persones?",
                    "a": "Jugadors, entrenadors i altres membres que pots vincular a equips. Això permet a AtempoSports detectar solapaments quan una mateixa persona és a dos llocs alhora.",
                    "link": "/season/{season_id}/people",
                },
                {
                    "q": "Com importo molts jugadors?",
                    "a": "A Persones pots enganxar noms separats per línies o per comes. Això és útil quan ja tens una llista del teu club.",
                },
            ],
        },
        {
            "id": "calendari",
            "title": "Calendari i partits",
            "questions": [
                {
                    "q": "Què veig al calendari?",
                    "a": "Els propers 28 dies amb partits federatius, entrenaments ja aplicats i qualsevol canvi pendent.",
                    "link": "/season/{season_id}/calendar",
                },
                {
                    "q": "Què signifiquen els colors?",
                    "a": "Verd = tot bé, groc = possible conflicte tou, vermell = conflicte dur que cal resoldre.",
                },
                {
                    "q": "Com moc un partit?",
                    "a": "Des de Partits o des del calendari pots editar l'hora. AtempoSports et dirà si el nou horari genera conflictes amb altres activitats.",
                    "link": "/season/{season_id}/matches",
                },
            ],
        },
        {
            "id": "entrenaments",
            "title": "Entrenaments",
            "questions": [
                {
                    "q": "Com genero entrenaments?",
                    "a": "Ves a Entrenaments, revisa les hores setmanals de cada equip i prem “Proposar”. AtempoSports farà un borrador repartint les sessions pel nombre de franges disponibles.",
                    "link": "/season/{season_id}/trainings",
                },
                {
                    "q": "Què és el borrador?",
                    "a": "És una proposta d'entrenaments que encara no està al calendari oficial. Pots modificar-la, descartar-la o aplicar-la.",
                },
                {
                    "q": "Com aplico els entrenaments?",
                    "a": "Si t'agrada el borrador, prem “Aplicar”. Això passa els entrenaments al calendari oficial i substitueix els entrenaments de l'últim lot aplicat.",
                },
                {
                    "q": "Puc desfer l'aplicació?",
                    "a": "Sí, mentre no hagis generat un borrador nou. Hi ha una opció “Desfer aplicació” que torna l'últim lot a borrador.",
                },
            ],
        },
        {
            "id": "grups",
            "title": "Grups",
            "questions": [
                {
                    "q": "Què és un grup?",
                    "a": "Un conjunt de dues o més unitats que comparteixen la mateixa franja sencera durant tota la temporada. Útil quan comparteixen entrenament.",
                    "link": "/season/{season_id}/trainings/groups",
                },
                {
                    "q": "Com creo un grup?",
                    "a": "Ves a Entrenaments → Grups i selecciona els equips o unitats que entrenaran junts. AtempoSports els assignarà una franja comuna.",
                },
            ],
        },
        {
            "id": "solapaments",
            "title": "Solapaments",
            "questions": [
                {
                    "q": "Què és un solapament?",
                    "a": "És la manera en que es produeix la transició entre dos equips a la mateixa pista. Per exemple, l'equip A entrena fins a les 19:00 i l'equip B comença a les 19:00. Es pot fer que se solapin 15 o més minuts un o diversos dies o tota la temporada. Que el solapament impliqui partició o no de la pista per a cada equip és una qüestió a decidir entre els entrenadors i el coordinador.",
                    "link": "/season/{season_id}/trainings/overlaps",
                },
                {
                    "q": "Per a què serveixen?",
                    "a": "Permeten aprofitar millor la pista quan els recursos són escassos."
                },
            ],
        },
        {
            "id": "conflictes",
            "title": "Conflictes",
            "questions": [
                {
                    "q": "Què és un conflicte dur?",
                    "a": "És quan el mateix equip o persona ha de ser a dos llocs alhora, o dues activitats coincideixen de manera incompatible.",
                    "link": "/season/{season_id}/conflicts",
                },
                {
                    "q": "Què és un conflicte tou?",
                    "a": "És una superposició o preferència que cal revisar, però que no impedeix l'activitat. AtempoSports t'ho marca perquè ho miris.",
                },
                {
                    "q": "Com resolc un conflicte?",
                    "a": "AtempoSports et proposa alternatives. Pots acceptar-les, modificar-les o, si prefereixes, canviar manualment l'activitat des del calendari.",
                },
            ],
        },
        {
            "id": "renovacio",
            "title": "Renovació de temporada",
            "questions": [
                {
                    "q": "Com començo una nova temporada?",
                    "a": "Ves a Temporades i prem “Renovar”. AtempoSports copia la configuració actual (equips, pistes i franges) i crea una nova temporada buida.",
                    "link": "/season/{season_id}/renew",
                },
                {
                    "q": "Què es copia?",
                    "a": "La nova temporada reaprofita l'esquelet de l'anterior: equips, pistes, franges i preferències. Això fa que el coordinador pugui ajustar persones, horaris i sessions a la nova temporada sense començar de zero. Els partits i entrenaments concrets, en canvi, no es copien; els tornes a crear o importar per la nova temporada."
                },
                {
                    "q": "Puc tenir més d'una temporada?",
                    "a": "Sí, però només una està activa per club. Pots canviar la temporada activa des del menú de temporades si ets l'operador.",
                },
            ],
        },
        {
            "id": "ajustos",
            "title": "Ajustos del club",
            "questions": [
                {
                    "q": "Com canvio el correu del club?",
                    "a": "A Ajustos del club (o Club) pots desar un correu nou. És important per poder recuperar la contrasenya.",
                    "link": "/season/{season_id}/club",
                },
                {
                    "q": "Com canvio la contrasenya?",
                    "a": "A la mateixa pàgina del club indica la contrasenya actual i la nova. Si no recordes l'actual, contacta amb qui et va donar l'accés.",
                },
            ],
        },
    ],
}


EXTRA_HELP: dict[str, list[dict]] = {
    "es": [
        {
            "id": "primeres-passos",
            "title": "Primeros pasos",
            "questions": [
                {
                    "q": "¿Cómo entro por primera vez?",
                    "a": "Escribe el código del club y la contraseña. Si la has olvidado, pulsa “¿He olvidado la contraseña?”. Recibirás un enlace en el correo del club si lo tenemos configurado.",
                    "link": "/login",
                },
                {
                    "q": "¿Cómo cambio la contraseña?",
                    "a": "Ve al menú del club (“Ajustes”) e introduce una contraseña nueva de al menos 8 caracteres. Asegúrate de recordarla o de tener un correo de recuperación.",
                    "link": "/season/{season_id}/club",
                },
                {
                    "q": "¿Puedo cambiar el idioma?",
                    "a": "Sí. Arriba a la derecha encontrarás un selector con todos los idiomas. El cambio afecta a toda la aplicación.",
                },
            ],
        },
        {
            "id": "federacio",
            "title": "Importar federación",
            "questions": [
                {
                    "q": "¿Cómo busco los partidos federativos?",
                    "a": "Ve a Importar, escribe el nombre de tu club y elige la federación (RFEP o FECAPA) y la comunidad autónoma. AtempoSports buscará las convocatorias disponibles.",
                    "link": "/season/{season_id}/fed",
                },
                {
                    "q": "¿Y si no encuentro mi club?",
                    "a": "Puedes añadir los equipos y los partidos manualmente desde las secciones Equipos y Partidos. La opción de búsqueda solo cubre España y sus comunidades autónomas actualmente.",
                },
                {
                    "q": "¿Se ven los cambios de la federación?",
                    "a": "Sí. Cuando la federación cambia horarios, AtempoSports lo detecta y te avisa en la página de inicio para que los revises antes de aplicarlos.",
                    "link": "/app",
                },
            ],
        },
        {
            "id": "pistes",
            "title": "Pistas y franjas",
            "questions": [
                {
                    "q": "¿Cómo añado una pista?",
                    "a": "Ve a Pistas y escribe el nombre. Después define las franjas horarias disponibles (por ejemplo, los lunes de 18:00 a 20:00).",
                    "link": "/season/{season_id}/venues",
                },
                {
                    "q": "¿Qué es una franja?",
                    "a": "Una franja es un horario en el que la pista está libre para entrenar o jugar. Puedes tener varias franjas por día y por pista.",
                },
                {
                    "q": "¿Puedo bloquear una franja?",
                    "a": "Si una franja no está disponible para entrenamientos, puedes marcarla o eliminarla. Solo las franjas activas se usan para generar propuestas.",
                },
            ],
        },
        {
            "id": "equips",
            "title": "Equipos y personas",
            "questions": [
                {
                    "q": "¿Cómo creo un equipo?",
                    "a": "Ve a Equipos y pulsa “Crear equipo”. Puedes escribir el nombre manualmente o pegar una lista de nombres si tienes muchos.",
                    "link": "/season/{season_id}/teams",
                },
                {
                    "q": "¿Qué son las personas?",
                    "a": "Jugadores, entrenadores y otros miembros que puedes vincular a equipos. Esto permite a AtempoSports detectar solapamientos cuando la misma persona está en dos sitios a la vez.",
                    "link": "/season/{season_id}/people",
                },
                {
                    "q": "¿Cómo importo muchos jugadores?",
                    "a": "En Personas puedes pegar nombres separados por líneas o por comas. Es útil cuando ya tienes una lista del club.",
                },
            ],
        },
        {
            "id": "calendari",
            "title": "Calendario y partidos",
            "questions": [
                {
                    "q": "¿Qué veo en el calendario?",
                    "a": "Los próximos 28 días con partidos federativos, entrenamientos ya aplicados y cualquier cambio pendiente.",
                    "link": "/season/{season_id}/calendar",
                },
                {
                    "q": "¿Qué significan los colores?",
                    "a": "Verde = todo bien, amarillo = posible conflicto blando, rojo = conflicto duro que hay que resolver.",
                },
                {
                    "q": "¿Cómo muevo un partido?",
                    "a": "Desde Partidos o desde el calendario puedes editar la hora. AtempoSports te dirá si el nuevo horario genera conflictos con otras actividades.",
                    "link": "/season/{season_id}/matches",
                },
            ],
        },
        {
            "id": "entrenaments",
            "title": "Entrenamientos",
            "questions": [
                {
                    "q": "¿Cómo genero entrenamientos?",
                    "a": "Ve a Entrenamientos, revisa las horas semanales de cada equipo y pulsa “Proponer”. AtempoSports hará un borrador repartiendo las sesiones según las franjas disponibles.",
                    "link": "/season/{season_id}/trainings",
                },
                {
                    "q": "¿Qué es el borrador?",
                    "a": "Es una propuesta de entrenamientos que aún no está en el calendario oficial. Puedes modificarla, descartarla o aplicarla.",
                },
                {
                    "q": "¿Cómo aplico los entrenamientos?",
                    "a": "Si te gusta el borrador, pulsa “Aplicar”. Esto pasa los entrenamientos al calendario oficial y sustituye los entrenamientos del último lote aplicado.",
                },
                {
                    "q": "¿Puedo deshacer la aplicación?",
                    "a": "Sí, mientras no hayas generado un borrador nuevo. Hay una opción “Deshacer aplicación” que devuelve el último lote a borrador.",
                },
            ],
        },
        {
            "id": "grups",
            "title": "Grupos",
            "questions": [
                {
                    "q": "¿Qué es un grupo?",
                    "a": "Un conjunto de dos o más unidades que comparten la misma franja entera durante toda la temporada. Útil cuando comparten entrenamiento.",
                    "link": "/season/{season_id}/trainings/groups",
                },
                {
                    "q": "¿Cómo creo un grupo?",
                    "a": "Ve a Entrenamientos → Grupos y selecciona los equipos o unidades que entrenarán juntos. AtempoSports les asignará una franja común.",
                },
            ],
        },
        {
            "id": "solapaments",
            "title": "Solapamientos",
            "questions": [
                {
                    "q": "¿Qué es un solapamiento?",
                    "a": "Es la manera en que se produce la transición entre dos equipos en la misma pista. Por ejemplo, el equipo A entrena hasta las 19:00 y el equipo B comienza a las 19:00. Se puede hacer que se solapen 15 o más minutos uno o varios días o toda la temporada. Que el solapamiento implique partición o no de la pista para cada equipo es una cuestión a decidir entre entrenadores y coordinador.",
                    "link": "/season/{season_id}/trainings/overlaps",
                },
                {
                    "q": "¿Para qué sirven?",
                    "a": "Permiten aprovechar mejor la pista cuando los recursos son escasos.",
                },
            ],
        },
        {
            "id": "conflictes",
            "title": "Conflictos",
            "questions": [
                {
                    "q": "¿Qué es un conflicto duro?",
                    "a": "Es cuando el mismo equipo o persona debe estar en dos sitios a la vez, o dos actividades del mismo club coinciden de manera incompatible.",
                    "link": "/season/{season_id}/conflicts",
                },
                {
                    "q": "¿Qué es un conflicto blando?",
                    "a": "Es una superposición o preferencia que conviene revisar, pero que no impide la actividad. AtempoSports te lo marca para que lo mires.",
                },
                {
                    "q": "¿Cómo resuelvo un conflicto?",
                    "a": "AtempoSports te propone alternativas. Puedes aceptarlas, modificarlas o, si prefieres, cambiar manualmente la actividad desde el calendario.",
                },
            ],
        },
        {
            "id": "renovacio",
            "title": "Renovación de temporada",
            "questions": [
                {
                    "q": "¿Cómo empiezo una nueva temporada?",
                    "a": "Ve a Temporadas y pulsa “Renovar”. AtempoSports copia la configuración actual (equipos, pistas y franjas) y crea una nueva temporada vacía.",
                    "link": "/season/{season_id}/renew",
                },
                {
                    "q": "¿Qué se copia?",
                    "a": "La nueva temporada reaprovecha el esqueleto de la anterior: equipos, pistas, franjas y preferencias. Esto permite que el coordinador ajuste personas, horarios y sesiones a la nueva temporada sin empezar de cero. Los partidos y entrenamientos concretos, en cambio, no se copian; los vuelves a crear o importar para la nueva temporada.",
                },
                {
                    "q": "¿Puedo tener más de una temporada?",
                    "a": "Sí, pero solo una está activa por club. Puedes cambiar la temporada activa desde el menú de temporadas si eres operador.",
                },
            ],
        },
        {
            "id": "ajustos",
            "title": "Ajustes del club",
            "questions": [
                {
                    "q": "¿Cómo cambio el correo del club?",
                    "a": "En Ajustes del club (o Club) puedes guardar un correo nuevo. Es importante para poder recuperar la contraseña.",
                    "link": "/season/{season_id}/club",
                },
                {
                    "q": "¿Cómo cambio la contraseña?",
                    "a": "En la misma página del club indica la contraseña actual y la nueva. Si no recuerdas la actual, contacta con quien te dio acceso.",
                },
            ],
        },
    ],
    "en": [
        {
            "id": "primeres-passos",
            "title": "First steps",
            "questions": [
                {
                    "q": "How do I log in for the first time?",
                    "a": "Enter the club code and password. If you forgot it, click “Forgot your password?”. You will receive a link at the club email if it is configured.",
                    "link": "/login",
                },
                {
                    "q": "How do I change the password?",
                    "a": "Go to the club menu (“Settings”) and enter a new password of at least 8 characters. Make sure you remember it or have a recovery email.",
                    "link": "/season/{season_id}/club",
                },
                {
                    "q": "Can I change the language?",
                    "a": "Yes. At the top right you will find a selector with all languages. The change affects the whole application.",
                },
            ],
        },
        {
            "id": "federacio",
            "title": "Federation import",
            "questions": [
                {
                    "q": "How do I find federation matches?",
                    "a": "Go to Import, type your club name and choose the federation (RFEP or FECAPA) and the autonomous community. AtempoSports will search for available fixtures.",
                    "link": "/season/{season_id}/fed",
                },
                {
                    "q": "What if I cannot find my club?",
                    "a": "You can add teams and matches manually from the Teams and Matches sections. The search option currently only covers Spain and its autonomous communities.",
                },
                {
                    "q": "Are federation changes reflected?",
                    "a": "Yes. When the federation changes times, AtempoSports detects it and alerts you on the home page so you can review them before applying.",
                    "link": "/app",
                },
            ],
        },
        {
            "id": "pistes",
            "title": "Venues and time slots",
            "questions": [
                {
                    "q": "How do I add a venue?",
                    "a": "Go to Venues and type the name. Then define the available time slots (for example, Mondays from 18:00 to 20:00).",
                    "link": "/season/{season_id}/venues",
                },
                {
                    "q": "What is a time slot?",
                    "a": "A slot is a time when the venue is free to train or play. You can have multiple slots per day and per venue.",
                },
                {
                    "q": "Can I block a slot?",
                    "a": "If a slot is not available for training, you can mark it or remove it. Only active slots are used to generate proposals.",
                },
            ],
        },
        {
            "id": "equips",
            "title": "Teams and people",
            "questions": [
                {
                    "q": "How do I create a team?",
                    "a": "Go to Teams and click “Create team”. You can type the name manually or paste a list of names if you have many.",
                    "link": "/season/{season_id}/teams",
                },
                {
                    "q": "What are people?",
                    "a": "Players, coaches and other members you can link to teams. This lets AtempoSports detect overlaps when the same person has to be in two places at once.",
                    "link": "/season/{season_id}/people",
                },
                {
                    "q": "How do I import many players?",
                    "a": "In People you can paste names separated by lines or commas. This is useful when you already have a club list.",
                },
            ],
        },
        {
            "id": "calendari",
            "title": "Calendar and matches",
            "questions": [
                {
                    "q": "What do I see in the calendar?",
                    "a": "The next 28 days with federation matches, applied trainings and any pending changes.",
                    "link": "/season/{season_id}/calendar",
                },
                {
                    "q": "What do the colours mean?",
                    "a": "Green = all good, yellow = possible soft conflict, red = hard conflict that needs resolving.",
                },
                {
                    "q": "How do I move a match?",
                    "a": "From Matches or the calendar you can edit the time. AtempoSports will tell you if the new time creates conflicts with other activities.",
                    "link": "/season/{season_id}/matches",
                },
            ],
        },
        {
            "id": "entrenaments",
            "title": "Trainings",
            "questions": [
                {
                    "q": "How do I generate trainings?",
                    "a": "Go to Trainings, review the weekly hours for each team and click “Propose”. AtempoSports will draft sessions spread across the available slots.",
                    "link": "/season/{season_id}/trainings",
                },
                {
                    "q": "What is the draft?",
                    "a": "It is a training proposal that is not yet in the official calendar. You can modify it, discard it or apply it.",
                },
                {
                    "q": "How do I apply the trainings?",
                    "a": "If you like the draft, click “Apply”. This moves the trainings to the official calendar and replaces the trainings from the last applied batch.",
                },
                {
                    "q": "Can I undo the application?",
                    "a": "Yes, as long as you have not generated a new draft. There is an “Undo application” option that reverts the last batch to draft.",
                },
            ],
        },
        {
            "id": "grups",
            "title": "Groups",
            "questions": [
                {
                    "q": "What is a group?",
                    "a": "Two or more units that share the same full slot throughout the season. Useful when they train together.",
                    "link": "/season/{season_id}/trainings/groups",
                },
                {
                    "q": "How do I create a group?",
                    "a": "Go to Trainings → Groups and select the teams or units that will train together. AtempoSports will assign them a common slot.",
                },
            ],
        },
        {
            "id": "solapaments",
            "title": "Overlaps",
            "questions": [
                {
                    "q": "What is an overlap?",
                    "a": "It is the way the transition happens between two teams on the same pitch. For example, team A trains until 19:00 and team B starts at 19:00. You can set an overlap of 15 or more minutes on one or several days or the whole season. Whether the overlap implies splitting the pitch for each team is a matter to decide between coaches and the coordinator.",
                    "link": "/season/{season_id}/trainings/overlaps",
                },
                {
                    "q": "What are they for?",
                    "a": "They let you make better use of the pitch when resources are scarce.",
                },
            ],
        },
        {
            "id": "conflictes",
            "title": "Conflicts",
            "questions": [
                {
                    "q": "What is a hard conflict?",
                    "a": "When the same team or person must be in two places at once, or two club activities clash incompatibly.",
                    "link": "/season/{season_id}/conflicts",
                },
                {
                    "q": "What is a soft conflict?",
                    "a": "An overlap or preference worth reviewing, but one that does not prevent the activity. AtempoSports marks it for you to check.",
                },
                {
                    "q": "How do I resolve a conflict?",
                    "a": "AtempoSports proposes alternatives. You can accept them, modify them or, if you prefer, change the activity manually from the calendar.",
                },
            ],
        },
        {
            "id": "renovacio",
            "title": "Season renewal",
            "questions": [
                {
                    "q": "How do I start a new season?",
                    "a": "Go to Seasons and click “Renew”. AtempoSports copies the current configuration (teams, venues and slots) and creates a new empty season.",
                    "link": "/season/{season_id}/renew",
                },
                {
                    "q": "What is copied?",
                    "a": "The new season reuses the previous skeleton: teams, venues, slots and preferences. This lets the coordinator adjust people, times and sessions to the new season without starting from scratch. Specific matches and trainings, however, are not copied; you create or import them again for the new season.",
                },
                {
                    "q": "Can I have more than one season?",
                    "a": "Yes, but only one is active per club. You can change the active season from the seasons menu if you are an operator.",
                },
            ],
        },
        {
            "id": "ajustos",
            "title": "Club settings",
            "questions": [
                {
                    "q": "How do I change the club email?",
                    "a": "In Club settings (or Club) you can save a new email. It is important for recovering access.",
                    "link": "/season/{season_id}/club",
                },
                {
                    "q": "How do I change the password?",
                    "a": "On the same club page enter the current password and the new one. If you do not remember the current one, contact whoever gave you access.",
                },
            ],
        },
    ],
    "eu": [
        {
            "id": "primeres-passos",
            "title": "Lehen pausoak",
            "questions": [
                {
                    "q": "Nola sartzen naiz lehen aldiz?",
                    "a": "Idatzi zure klubaren kodea eta pasahitza. Ahaztu baduzu, sakatu “Pasahitza ahaztu dut?”. Konfiguratuta badugu, korreo bidez esteka bat jasoko duzu.",
                    "link": "/login",
                },
                {
                    "q": "Nola aldatu dezaket pasahitza?",
                    "a": "Zoaz klubaren menuan ('Ezarpenak') eta idatzi gutxienez 8 karaktereko pasahitz berria. Gogoan izan edo berreskuratzeko korreoa izan ezazu.",
                    "link": "/season/{season_id}/club",
                },
                {
                    "q": "Hizkuntza aldatu dezaket?",
                    "a": "Bai. Goian eskuinean hizkuntza-hautatzaile bat aurkituko duzu hizkunta guztiekin. Aldaketak aplikazio osoan eragiten du.",
                },
            ],
        },
        {
            "id": "federacio",
            "title": "Federazioa inportatu",
            "questions": [
                {
                    "q": "Nola bilatu ditzakedan partidu federatiboak?",
                    "a": "Zoaz Inportatzera, idatzi zure klubaren izena eta aukeratu federazioa (RFEP edo FECAPA) eta autonomia erkidegoa. AtempoSports-k eskuragarri dauden deialdiak bilatuko ditu.",
                    "link": "/season/{season_id}/fed",
                },
                {
                    "q": "Eta ez badut nire kluba aurkitzen?",
                    "a": "Eskuz gehitu ditzakezu taldeak eta partiduak Taldeak eta Partiduak ataletatik. Bilaketa aukera, oraingoz, Espainia eta bere autonomia erkidegoak baino ez ditu estaltzen.",
                },
                {
                    "q": "Federazioaren aldaketak ikusten dira?",
                    "a": "Bai. Federazioak ordutegiak aldatzen dituenean, AtempoSports-k hautematen du eta hasierako orrian jakinaraziko dizu, aplikatu aurretik berrikusteko.",
                    "link": "/app",
                },
            ],
        },
        {
            "id": "pistes",
            "title": "Pistak eta ordutegi-tarteak",
            "questions": [
                {
                    "q": "Nola gehitu dezaket pista bat?",
                    "a": "Zoaz Pistetara eta idatzi izena. Ondoren zehaztu eskuragarri dauden ordutegi-tarteak (adibidez, astelehenetan 18:00tik 20:00ra).",
                    "link": "/season/{season_id}/venues",
                },
                {
                    "q": "Zer da ordutegi-tarte bat?",
                    "a": "Tarte bat pista entrenatzeko edo jokatzeko libre dagoen ordutegia da. Hainbat tarte izan ditzakezu eguneko eta pistako.",
                },
                {
                    "q": "Tarte bat blokea dezaket?",
                    "a": "Tarte bat ez badago eskuragarri entrenamentuetarako, markatu edo ezaba dezakezu. Tarte aktiboak bakarrik erabiliko dira proposamenak sortzeko.",
                },
            ],
        },
        {
            "id": "equips",
            "title": "Taldeak eta pertsonak",
            "questions": [
                {
                    "q": "Nola sor dezaket talde bat?",
                    "a": "Zoaz Taldeetara eta sakatu 'Sortu taldea'. Eskuz idatz dezakezu izena edo izenen zerrenda itsatsi, asko badituzu.",
                    "link": "/season/{season_id}/teams",
                },
                {
                    "q": "Zer dira pertsonak?",
                    "a": "Jokalariak, entrenatzaileak eta taldeekin lotu ditzakezun beste kide batzuk. Horri esker, AtempoSports-k gainjartzeak detektatu ditzake pertsona bera bi lekutan egonez gero.",
                    "link": "/season/{season_id}/people",
                },
                {
                    "q": "Nola inportatu ditzakedan jokalari asko?",
                    "a": "Pertsonak atalean izenak lerro edo komen bidez itsats ditzakezu. Erabilgarria da klubeko zerrenda bat baduzu.",
                },
            ],
        },
        {
            "id": "calendari",
            "title": "Egutegia eta partiduak",
            "questions": [
                {
                    "q": "Zer ikusten dut egutegian?",
                    "a": "Hurrengo 28 egunak partidu federatiboekin, aplikatutako entrenamenduekin eta aldaketa zain dauden guztiekin.",
                    "link": "/season/{season_id}/calendar",
                },
                {
                    "q": "Zer esan nahi dute koloreek?",
                    "a": "Berdea = dena ondo, horia = gatazka bigun posiblea, gorria = gatazka gogorra konpondu beharrekoa.",
                },
                {
                    "q": "Nola mugitu dezaket partidu bat?",
                    "a": "Partiduak edo egutegitik ordua editatu dezakezu. AtempoSports-k esango dizu ordutegi berriak gatazkak sortzen dituen beste jardueren artean.",
                    "link": "/season/{season_id}/matches",
                },
            ],
        },
        {
            "id": "entrenaments",
            "title": "Entrenamenduak",
            "questions": [
                {
                    "q": "Nola sortu ditzakedan entrenamenduak?",
                    "a": "Zoaz Entrenamenduetara, berrikusi talde bakoitzeko asteeko orduak eta sakatu 'Proposatu'. AtempoSports-k zirriborro bat egingo du eskuragarri dauden tarteen arabera.",
                    "link": "/season/{season_id}/trainings",
                },
                {
                    "q": "Zer da zirriborroa?",
                    "a": "Oraindik egutegi ofizialean ez dagoen entrenamendu-proposamen bat da. Aldatu, baztertu edo aplika dezakezu.",
                },
                {
                    "q": "Nola aplikatu ditzakedan entrenamenduak?",
                    "a": "Zirriborroa gustuko baduzu, sakatu 'Aplikatu'. Horrek entrenamenduak egutegi ofizialera pasatuko ditu eta azken loteko entrenamenduak ordezkatuko ditu.",
                },
                {
                    "q": "Aplikazioa desegin dezaket?",
                    "a": "Bai, zirriborro berri bat sortu ez baduzu. 'Desegin aplikazioa' aukera dago, azken lotea zirriborrora itzultzeko.",
                },
            ],
        },
        {
            "id": "grups",
            "title": "Taldeak multzo",
            "questions": [
                {
                    "q": "Zer da multzo bat?",
                    "a": "Bi edo unitate gehiago denboraldi osoan zehar tarte bera partekatzen dutenak. Entrenamendua partekatzen dutenean erabilgarria.",
                    "link": "/season/{season_id}/trainings/groups",
                },
                {
                    "q": "Nola sor dezaket multzo bat?",
                    "a": "Zoaz Entrenamenduak → Multzoak eta aukeratu elkarrekin entrenatuko diren taldeak edo unitateak. AtempoSports-k tarte komun bat esleituko die.",
                },
            ],
        },
        {
            "id": "solapaments",
            "title": "Gainjartzeak",
            "questions": [
                {
                    "q": "Zer da gainjartze bat?",
                    "a": "Pista berean bi taldearen artean trantsizioa gertatzen den modua da. Adibidez, A taldea 19:00ra arte entrenatzen du eta B taldea 19:00etan hasten da. 15 minutu edo gehiagoko gainjartzea egin daiteke egun batzuetan edo denboraldi osoan. Gainjartzeak pista zatitu edo ez zatitu behar duen talde bakoitzarentzat entrenatzaileen eta koordinatzailearen artean erabakitako kontua da.",
                    "link": "/season/{season_id}/trainings/overlaps",
                },
                {
                    "q": "Zertarako balio dute?",
                    "a": "Baliabideak urriak direnean pista hobeto aprobetxatzeko aukera ematen dute.",
                },
            ],
        },
        {
            "id": "conflictes",
            "title": "Gatazkak",
            "questions": [
                {
                    "q": "Zer da gatazka gogor bat?",
                    "a": "Talde edo pertsona bera une berean bi lekutan egon behar duenean, edo bi jarduera bateraezinak direnean.",
                    "link": "/season/{season_id}/conflicts",
                },
                {
                    "q": "Zer da gatazka bigun bat?",
                    "a": "Berrikusteko balio duen gainjartze edo hobespen bat da, baina ez du jarduerarako oztopatzen. AtempoSports-k markatuko dizu ikusteko.",
                },
                {
                    "q": "Nola konpondu dezaket gatazka bat?",
                    "a": "AtempoSports-k aukera proposatuko dizkizu. Onartu, aldatu edo, nahiago baduzu, egutegitik eskuz aldatu dezakezu jarduera.",
                },
            ],
        },
        {
            "id": "renovacio",
            "title": "Denboraldia berritu",
            "questions": [
                {
                    "q": "Nola hasi dezaket denboraldi berri bat?",
                    "a": "Zoaz Denboraldiak eta sakatu 'Berritu'. AtempoSports-k uneko konfigurazioa kopiatuko du (taldeak, pistak eta tarteak) eta denboraldi hutsa bat sortuko du.",
                    "link": "/season/{season_id}/renew",
                },
                {
                    "q": "Zer kopiatzen da?",
                    "a": "Denboraldi berriak aurrekoaren hezurdura aprobetxatzen du: taldeak, pistak, tarteak eta hobespenak. Horri esker, koordinatzaileak pertsonak, ordutegiak eta saioak doitu ditzake denboraldi berrira hasieratik hasi gabe. Partidu eta entrenamendu zehatzak, ordea, ez dira kopiatzen; berriro sortu edo inportatu behar dira denboraldi berrirako.",
                },
                {
                    "q": "Denboraldi bat baino gehiago izan ditzakedan?",
                    "a": "Bai, baina klubeko bat bakarrik dago aktibo. Operatzailea bazara, denboraldiak menuan alda dezakezu aktiboa.",
                },
            ],
        },
        {
            "id": "ajustos",
            "title": "Klubaren ezarpenak",
            "questions": [
                {
                    "q": "Nola aldatu dezaket klubaren korreoa?",
                    "a": "Klubaren ezarpenetan (edo Kluba) korreo berria gorde dezakezu. Garrantzitsua da sarbidea berreskuratzeko.",
                    "link": "/season/{season_id}/club",
                },
                {
                    "q": "Nola aldatu dezaket pasahitza?",
                    "a": "Klubaren orri berean sartu uneko pasahitza eta berria. Uneko pasahitza gogoan ez baduzu, jarri harremanetan sarbidea eman zizuenarekin.",
                },
            ],
        },
    ],
    "gl": [
        {
            "id": "primeres-passos",
            "title": "Primeiros pasos",
            "questions": [
                {
                    "q": "Como entro por primeira vez?",
                    "a": "Escribe o código do teu club e o teu contrasinal. Se o esquecestes, preme 'Esquecín o contrasinal?'. Recibirás unha liga ao correo do club se o temos configurado.",
                    "link": "/login",
                },
                {
                    "q": "Como cambio o contrasinal?",
                    "a": "Vai ao menú do club ('Axustes') e pon un contrasinal novo de polo menos 8 caracteres. Asegúrate de lembralo ou de ter un correo de recuperación.",
                    "link": "/season/{season_id}/club",
                },
                {
                    "q": "Podo cambiar o idioma?",
                    "a": "Si. Arriba á dereita atoparás un selector con todos os idiomas. O cambio afecta toda a aplicación.",
                },
            ],
        },
        {
            "id": "federacio",
            "title": "Importar federación",
            "questions": [
                {
                    "q": "Como busco os partidos federativos?",
                    "a": "Vai a Importar, escribe o nome do teu club e escolle a federación (RFEP ou FECAPA) e a comunidade autónoma. AtempoSports buscará as convocatorias dispoñibles.",
                    "link": "/season/{season_id}/fed",
                },
                {
                    "q": "E se non atopo o meu club?",
                    "a": "Podes engadir equipos e partidos manualmente desde as seccións Equipos e Partidos. A opción de busca só cobre España e as súas comunidades autónomas actualmente.",
                },
                {
                    "q": "Vense os cambios da federación?",
                    "a": "Si. Cando a federación cambia horarios, AtempoSports detectao e avisarache na páxina de inicio para que os revises antes de aplicalos.",
                    "link": "/app",
                },
            ],
        },
        {
            "id": "pistes",
            "title": "Pistas e franxas",
            "questions": [
                {
                    "q": "Como engado unha pista?",
                    "a": "Vai a Pistas e escribe o nome. Despois define as franxas horarias dispoñibles (por exemplo, os luns de 18:00 a 20:00).",
                    "link": "/season/{season_id}/venues",
                },
                {
                    "q": "Que é unha franxa?",
                    "a": "Unha franxa é un horario no que a pista está libre para adestrar ou xogar. Podes ter varias franxas por día e por pista.",
                },
                {
                    "q": "Podo bloquear unha franxa?",
                    "a": "Se unha franxa non está dispoñible para adestramentos, podes marcala ou eliminala. Só as franxas activas usaranse para xerar propostas.",
                },
            ],
        },
        {
            "id": "equips",
            "title": "Equipos e persoas",
            "questions": [
                {
                    "q": "Como creo un equipo?",
                    "a": "Vai a Equipos e preme 'Crear equipo'. Podes escribir o nome manualmente ou pegar unha lista de nomes se tes moitos.",
                    "link": "/season/{season_id}/teams",
                },
                {
                    "q": "Que son as persoas?",
                    "a": "Xogadores, adestradores e outros membros que podes vincular a equipos. Isto permite a AtempoSports detectar solapamentos cando a mesma persoa estea dous sitios ao mesmo tempo.",
                    "link": "/season/{season_id}/people",
                },
                {
                    "q": "Como importo moitos xogadores?",
                    "a": "En Persoas podes pegar nomes separados por liñas ou por comas. É útil cando xa tes unha lista do club.",
                },
            ],
        },
        {
            "id": "calendari",
            "title": "Calendario e partidos",
            "questions": [
                {
                    "q": "Que vexo no calendario?",
                    "a": "Os próximos 28 días con partidos federativos, adestramentos xa aplicados e calquera cambio pendente.",
                    "link": "/season/{season_id}/calendar",
                },
                {
                    "q": "Que significan as cores?",
                    "a": "Verde = todo ben, amarelo = posible conflito brando, vermello = conflito duro que hai que resolver.",
                },
                {
                    "q": "Como movo un partido?",
                    "a": "Desde Partidos ou desde o calendario podes editar a hora. AtempoSports dirache se o novo horario xera conflitos con outras actividades.",
                    "link": "/season/{season_id}/matches",
                },
            ],
        },
        {
            "id": "entrenaments",
            "title": "Adestramentos",
            "questions": [
                {
                    "q": "Como xero adestramentos?",
                    "a": "Vai a Adestramentos, revisa as horas semanais de cada equipo e preme 'Propoñer'. AtempoSports fará un borrador repartindo as sesións segundo as franxas dispoñibles.",
                    "link": "/season/{season_id}/trainings",
                },
                {
                    "q": "Que é o borrador?",
                    "a": "É unha proposta de adestramentos que aínda non está no calendario oficial. Podes modificala, descartala ou aplicala.",
                },
                {
                    "q": "Como aplico os adestramentos?",
                    "a": "Se che gusta o borrador, preme 'Aplicar'. Isto pasa os adestramentos ao calendario oficial e substitúe os adestramentos do último lote aplicado.",
                },
                {
                    "q": "Podo desfacer a aplicación?",
                    "a": "Si, mentres non xeres un borrador novo. Hai unha opción 'Desfacer aplicación' que devolve o último lote a borrador.",
                },
            ],
        },
        {
            "id": "grups",
            "title": "Grupos",
            "questions": [
                {
                    "q": "Que é un grupo?",
                    "a": "Un conxunto de dúas ou máis unidades que comparten a mesma franxa enteira durante toda a tempada. Útil cando comparten adestramento.",
                    "link": "/season/{season_id}/trainings/groups",
                },
                {
                    "q": "Como creo un grupo?",
                    "a": "Vai a Adestramentos → Grupos e selecciona os equipos ou unidades que adestrarán xuntos. AtempoSports asignaralles unha franxa común.",
                },
            ],
        },
        {
            "id": "solapaments",
            "title": "Solapamentos",
            "questions": [
                {
                    "q": "Que é un solapamento?",
                    "a": "É a maneira na que se produce a transición entre dous equipos na mesma pista. Por exemplo, o equipo A adestra ata as 19:00 e o equipo B comeza as 19:00. Pódeselle facer que se solapen 15 ou máis minutos un ou varios días ou toda a tempada. Que o solapamento implique partición ou non da pista para cada equipo é unha cuestión a decidir entre os adestradores e o coordinador.",
                    "link": "/season/{season_id}/trainings/overlaps",
                },
                {
                    "q": "Para que serven?",
                    "a": "Permiten aproveitar mellor a pista cando os recursos son escasos.",
                },
            ],
        },
        {
            "id": "conflictes",
            "title": "Conflitos",
            "questions": [
                {
                    "q": "Que é un conflito duro?",
                    "a": "É cando o mesmo equipo ou persoa debe estar dous sitios ao mesmo tempo, ou dúas actividades do mesmo club coinciden de maneira incompatible.",
                    "link": "/season/{season_id}/conflicts",
                },
                {
                    "q": "Que é un conflito brando?",
                    "a": "É unha superposición ou preferencia que convén revisar, pero que non impide a actividade. AtempoSports marcacho para que o mires.",
                },
                {
                    "q": "Como resolvo un conflito?",
                    "a": "AtempoSports proponche alternativas. Podes aceptalas, modificalas ou, se prefires, cambiar manualmente a actividade desde o calendario.",
                },
            ],
        },
        {
            "id": "renovacio",
            "title": "Renovación de tempada",
            "questions": [
                {
                    "q": "Como comezo unha nova tempada?",
                    "a": "Vai a Tempadas e preme 'Renovar'. AtempoSports copia a configuración actual (equipos, pistas e franxas) e crea unha tempada baleira.",
                    "link": "/season/{season_id}/renew",
                },
                {
                    "q": "Que se copia?",
                    "a": "A nova tempada reaproveita o esqueleto da anterior: equipos, pistas, franxas e preferencias. Isto permite que o coordinador axuste persoas, horarios e sesións á nova tempada sen comezar de cero. Os partidos e adestramentos concretos, en cambio, non se copian; volves a crear ou importar para a nova tempada.",
                },
                {
                    "q": "Podo ter máis dunha tempada?",
                    "a": "Si, pero so unha está activa por club. Podes cambiar a tempada activa desde o menú de tempadas se es operador.",
                },
            ],
        },
        {
            "id": "ajustos",
            "title": "Axustes do club",
            "questions": [
                {
                    "q": "Como cambio o correo do club?",
                    "a": "En Axustes do club (ou Club) podes gardar un correo novo. É importante para poder recuperar o contrasinal.",
                    "link": "/season/{season_id}/club",
                },
                {
                    "q": "Como cambio o contrasinal?",
                    "a": "Na mesma páxina do club indica o contrasinal actual e o novo. Se non lembras o actual, contacta con quen che deu acceso.",
                },
            ],
        },
    ],
    "pt": [
        {
            "id": "primeres-passos",
            "title": "Primeiros passos",
            "questions": [
                {
                    "q": "Como entro pela primeira vez?",
                    "a": "Escreve o código do teu clube e a tua palavra-passe. Se a esqueceste, clica em 'Esqueci-me da palavra-passe?'. Receberás uma ligação no email do clube se estiver configurado.",
                    "link": "/login",
                },
                {
                    "q": "Como altero a palavra-passe?",
                    "a": "Vai ao menu do clube ('Definições') e introduz uma palavra-passe nova com pelo menos 8 caracteres. Certifica-te de que a lembras ou de ter um email de recuperação.",
                    "link": "/season/{season_id}/club",
                },
                {
                    "q": "Posso mudar o idioma?",
                    "a": "Sim. No topo à direita encontras um seletor com todos os idiomas. A mudança afeta toda a aplicação.",
                },
            ],
        },
        {
            "id": "federacio",
            "title": "Importar federação",
            "questions": [
                {
                    "q": "Como procuro os jogos federativos?",
                    "a": "Vai a Importar, escreve o nome do teu clube e escolhe a federação (RFEP ou FECAPA) e a comunidade autónoma. O AtempoSports procurará as convocatórias disponíveis.",
                    "link": "/season/{season_id}/fed",
                },
                {
                    "q": "E se não encontrar o meu clube?",
                    "a": "Podes adicionar equipas e jogos manualmente a partir das secções Equipas e Jogos. A opção de pesquisa cobre atualmente apenas Espanha e as suas comunidades autónomas.",
                },
                {
                    "q": "As mudanças da federação são visíveis?",
                    "a": "Sim. Quando a federação altera horários, o AtempoSports deteta e avisa-te na página inicial para que os revejas antes de aplicar.",
                    "link": "/app",
                },
            ],
        },
        {
            "id": "pistes",
            "title": "Pistas e franjas horárias",
            "questions": [
                {
                    "q": "Como adiciono uma pista?",
                    "a": "Vai a Pistas e escreve o nome. Depois define as franjas horárias disponíveis (por exemplo, às segundas das 18:00 às 20:00).",
                    "link": "/season/{season_id}/venues",
                },
                {
                    "q": "O que é uma franja horária?",
                    "a": "Uma franja é um horário em que a pista está livre para treinar ou jogar. Podes ter várias franjas por dia e por pista.",
                },
                {
                    "q": "Posso bloquear uma franja?",
                    "a": "Se uma franja não estiver disponível para treinos, podes marcá-la ou removê-la. Apenas as franjas ativas são usadas para gerar propostas.",
                },
            ],
        },
        {
            "id": "equips",
            "title": "Equipas e pessoas",
            "questions": [
                {
                    "q": "Como crio uma equipa?",
                    "a": "Vai a Equipas e clica em 'Criar equipa'. Podes escrever o nome manualmente ou colar uma lista de nomes se tiveres muitos.",
                    "link": "/season/{season_id}/teams",
                },
                {
                    "q": "Quem são as pessoas?",
                    "a": "Jogadores, treinadores e outros membros que podes vincular a equipas. Isto permite ao AtempoSports detetar sobreposições quando a mesma pessoa tem de estar em dois sítios ao mesmo tempo.",
                    "link": "/season/{season_id}/people",
                },
                {
                    "q": "Como importo muitos jogadores?",
                    "a": "Em Pessoas podes colar nomes separados por linhas ou vírgulas. É útil quando já tens uma lista do clube.",
                },
            ],
        },
        {
            "id": "calendari",
            "title": "Calendário e jogos",
            "questions": [
                {
                    "q": "O que vejo no calendário?",
                    "a": "Os próximos 28 dias com jogos federativos, treinos já aplicados e quaisquer alterações pendentes.",
                    "link": "/season/{season_id}/calendar",
                },
                {
                    "q": "O que significam as cores?",
                    "a": "Verde = tudo bem, amarelo = possível conflito brando, vermelho = conflito duro que precisa de resolução.",
                },
                {
                    "q": "Como movo um jogo?",
                    "a": "Em Jogos ou no calendário podes editar a hora. O AtempoSports dir-te-á se o novo horário cria conflitos com outras atividades.",
                    "link": "/season/{season_id}/matches",
                },
            ],
        },
        {
            "id": "entrenaments",
            "title": "Treinos",
            "questions": [
                {
                    "q": "Como gero treinos?",
                    "a": "Vai a Treinos, revisa as horas semanais de cada equipa e clica em 'Propor'. O AtempoSports fará um rascunho distribuindo as sessões pelas franjas disponíveis.",
                    "link": "/season/{season_id}/trainings",
                },
                {
                    "q": "O que é o rascunho?",
                    "a": "É uma proposta de treinos que ainda não está no calendário oficial. Podes modificá-la, descartá-la ou aplicá-la.",
                },
                {
                    "q": "Como aplico os treinos?",
                    "a": "Se gostares do rascunho, clica em 'Aplicar'. Isto passa os treinos para o calendário oficial e substitui os treinos do último lote aplicado.",
                },
                {
                    "q": "Posso desfazer a aplicação?",
                    "a": "Sim, desde que não tenhas gerado um rascunho novo. Há uma opção 'Desfazer aplicação' que volta com o último lote para rascunho.",
                },
            ],
        },
        {
            "id": "grups",
            "title": "Grupos",
            "questions": [
                {
                    "q": "O que é um grupo?",
                    "a": "Um conjunto de duas ou mais unidades que partilham a mesma franja completa durante toda a época. Útil quando treinam juntas.",
                    "link": "/season/{season_id}/trainings/groups",
                },
                {
                    "q": "Como crio um grupo?",
                    "a": "Vai a Treinos → Grupos e seleciona as equipas ou unidades que vão treinar juntas. O AtempoSports atribuir-lhes-á uma franja comum.",
                },
            ],
        },
        {
            "id": "solapaments",
            "title": "Sobreposições",
            "questions": [
                {
                    "q": "O que é uma sobreposição?",
                    "a": "É a forma como acontece a transição entre duas equipas na mesma pista. Por exemplo, a equipa A treina até as 19:00 e a equipa B começa às 19:00. Pode fazer-se com 15 ou mais minutos de sobreposição num ou vários dias ou toda a época. Se a sobreposição implica partilhar ou não a pista para cada equipa é uma questão a decidir entre os treinadores e o coordenador.",
                    "link": "/season/{season_id}/trainings/overlaps",
                },
                {
                    "q": "Para que servem?",
                    "a": "Permitem aproveitar melhor a pista quando os recursos são escassos.",
                },
            ],
        },
        {
            "id": "conflictes",
            "title": "Conflitos",
            "questions": [
                {
                    "q": "O que é um conflito duro?",
                    "a": "É quando a mesma equipa ou pessoa tem de estar em dois sítios ao mesmo tempo, ou quando duas atividades do mesmo clube coincidem de forma incompatível.",
                    "link": "/season/{season_id}/conflicts",
                },
                {
                    "q": "O que é um conflito brando?",
                    "a": "É uma sobreposição ou preferência que convém rever, mas que não impede a atividade. O AtempoSports assinala-te isso para verificares.",
                },
                {
                    "q": "Como resolvo um conflito?",
                    "a": "O AtempoSports propõe alternativas. Podes aceitá-las, modificá-las ou, se preferires, alterar manualmente a atividade a partir do calendário.",
                },
            ],
        },
        {
            "id": "renovacio",
            "title": "Renovação de época",
            "questions": [
                {
                    "q": "Como começo uma nova época?",
                    "a": "Vai a Épocas e clica em 'Renovar'. O AtempoSports copia a configuração atual (equipas, pistas e franjas) e cria uma época vazia.",
                    "link": "/season/{season_id}/renew",
                },
                {
                    "q": "O que é copiado?",
                    "a": "A nova época reaproveita a estrutura da anterior: equipas, pistas, franjas e preferências. Isto permite que o coordenador ajuste pessoas, horários e sessões à nova época sem começar de zero. Os jogos e treinos concretos, porém, não são copiados; tens de os criar ou importar novamente para a nova época.",
                },
                {
                    "q": "Posso ter mais do que uma época?",
                    "a": "Sim, mas só uma está ativa por clube. Podes alterar a época ativa no menu de Épocas se fores operador.",
                },
            ],
        },
        {
            "id": "ajustos",
            "title": "Definições do clube",
            "questions": [
                {
                    "q": "Como altero o email do clube?",
                    "a": "Em Definições do clube (ou Clube) podes guardar um email novo. É importante para poder recuperar o acesso.",
                    "link": "/season/{season_id}/club",
                },
                {
                    "q": "Como altero a palavra-passe?",
                    "a": "Na mesma página do clube indica a palavra-passe atual e a nova. Se não te lembras da atual, contacta quem te deu acesso.",
                },
            ],
        },
    ],
    "fr": [
        {
            "id": "primeres-passos",
            "title": "Premiers pas",
            "questions": [
                {
                    "q": "Comment me connecter pour la première fois ?",
                    "a": "Saisissez le code du club et le mot de passe. Si vous l'avez oublié, cliquez sur 'Mot de passe oublié ?'. Vous recevrez un lien par email du club si nous l'avons configuré.",
                    "link": "/login",
                },
                {
                    "q": "Comment changer le mot de passe ?",
                    "a": "Allez dans le menu du club ('Paramètres') et saisissez un nouveau mot de passe d'au moins 8 caractères. Assurez-vous de le mémoriser ou d'avoir un email de récupération.",
                    "link": "/season/{season_id}/club",
                },
                {
                    "q": "Puis-je changer la langue ?",
                    "a": "Oui. En haut à droite, vous trouverez un sélecteur avec toutes les langues. Le changement s'applique à toute l'application.",
                },
            ],
        },
        {
            "id": "federacio",
            "title": "Importer la fédération",
            "questions": [
                {
                    "q": "Comment rechercher les matchs fédéraux ?",
                    "a": "Allez dans Importer, saisissez le nom de votre club et choisissez la fédération (RFEP ou FECAPA) et la communauté autonome. AtempoSports recherchera les convocations disponibles.",
                    "link": "/season/{season_id}/fed",
                },
                {
                    "q": "Et si je ne trouve pas mon club ?",
                    "a": "Vous pouvez ajouter les équipes et les matchs manuellement depuis les sections Équipes et Matchs. L'option de recherche couvre actuellement l'Espagne et ses communautés autonomes.",
                },
                {
                    "q": "Les changements de la fédération sont-ils visibles ?",
                    "a": "Oui. Lorsque la fédération modifie des horaires, AtempoSports le détecte et vous alerte sur la page d'accueil pour les vérifier avant de les appliquer.",
                    "link": "/app",
                },
            ],
        },
        {
            "id": "pistes",
            "title": "Terrains et créneaux",
            "questions": [
                {
                    "q": "Comment ajouter un terrain ?",
                    "a": "Allez dans Terrains et saisissez le nom. Définissez ensuite les créneaux horaires disponibles (par exemple, le lundi de 18h00 à 20h00).",
                    "link": "/season/{season_id}/venues",
                },
                {
                    "q": "Qu'est-ce qu'un créneau ?",
                    "a": "Un créneau est un horaire pendant lequel le terrain est libre pour s'entraîner ou jouer. Vous pouvez avoir plusieurs créneaux par jour et par terrain.",
                },
                {
                    "q": "Puis-je bloquer un créneau ?",
                    "a": "Si un créneau n'est pas disponible pour les entraînements, vous pouvez le marquer ou le supprimer. Seuls les créneaux actifs sont utilisés pour générer des propositions.",
                },
            ],
        },
        {
            "id": "equips",
            "title": "Équipes et personnes",
            "questions": [
                {
                    "q": "Comment créer une équipe ?",
                    "a": "Allez dans Équipes et cliquez sur 'Créer une équipe'. Vous pouvez saisir le nom manuellement ou coller une liste de noms si vous en avez beaucoup.",
                    "link": "/season/{season_id}/teams",
                },
                {
                    "q": "Que sont les personnes ?",
                    "a": "Joueurs, entraîneurs et autres membres que vous pouvez lier aux équipes. Cela permet à AtempoSports de détecter les chevauchements lorsque la même personne doit être en deux endroits à la fois.",
                    "link": "/season/{season_id}/people",
                },
                {
                    "q": "Comment importer beaucoup de joueurs ?",
                    "a": "Dans Personnes, vous pouvez coller des noms séparés par des lignes ou des virgules. C'est utile si vous avez déjà une liste du club.",
                },
            ],
        },
        {
            "id": "calendari",
            "title": "Calendrier et matchs",
            "questions": [
                {
                    "q": "Que vois-je dans le calendrier ?",
                    "a": "Les 28 prochains jours avec les matchs fédéraux, les entraînements déjà appliqués et tous les changements en attente.",
                    "link": "/season/{season_id}/calendar",
                },
                {
                    "q": "Que signifient les couleurs ?",
                    "a": "Vert = tout va bien, jaune = conflit soft possible, rouge = conflit dur à résoudre.",
                },
                {
                    "q": "Comment déplacer un match ?",
                    "a": "Depuis Matchs ou depuis le calendrier, vous pouvez modifier l'heure. AtempoSports vous indiquera si le nouvel horaire crée des conflits avec d'autres activités.",
                    "link": "/season/{season_id}/matches",
                },
            ],
        },
        {
            "id": "entrenaments",
            "title": "Entraînements",
            "questions": [
                {
                    "q": "Comment générer des entraînements ?",
                    "a": "Allez dans Entraînements, vérifiez les heures hebdomadaires de chaque équipe et cliquez sur 'Proposer'. AtempoSports dressera un brouillon en répartissant les sessions selon les créneaux disponibles.",
                    "link": "/season/{season_id}/trainings",
                },
                {
                    "q": "Qu'est-ce que le brouillon ?",
                    "a": "C'est une proposition d'entraînements qui n'est pas encore dans le calendrier officiel. Vous pouvez la modifier, la supprimer ou l'appliquer.",
                },
                {
                    "q": "Comment appliquer les entraînements ?",
                    "a": "Si le brouillon vous convient, cliquez sur 'Appliquer'. Cela déplace les entraînements vers le calendrier officiel et remplace ceux du dernier lot appliqué.",
                },
                {
                    "q": "Puis-je annuler l'application ?",
                    "a": "Oui, tant que vous n'avez pas généré un nouveau brouillon. Il y a une option 'Annuler l'application' qui ramène le dernier lot en brouillon.",
                },
            ],
        },
        {
            "id": "grups",
            "title": "Groupes",
            "questions": [
                {
                    "q": "Qu'est-ce qu'un groupe ?",
                    "a": "Deux unités ou plus qui partagent le même créneau complet tout au long de la saison. Utile lorsqu'elles s'entraînent ensemble.",
                    "link": "/season/{season_id}/trainings/groups",
                },
                {
                    "q": "Comment créer un groupe ?",
                    "a": "Allez dans Entraînements → Groupes et sélectionnez les équipes ou unités qui s'entraîneront ensemble. AtempoSports leur attribuera un créneau commun.",
                },
            ],
        },
        {
            "id": "solapaments",
            "title": "Chevauchements",
            "questions": [
                {
                    "q": "Qu'est-ce qu'un chevauchement ?",
                    "a": "C'est la manière dont la transition se produit entre deux équipes sur le même terrain. Par exemple, l'équipe A s'entraîne jusqu'à 19h00 et l'équipe B commence à 19h00. On peut faire se chevaucher 15 minutes ou plus un ou plusieurs jours ou toute la saison. Que le chevauchement implique ou non le partage du terrain pour chaque équipe est une question à décider entre les entraîneurs et le coordinateur.",
                    "link": "/season/{season_id}/trainings/overlaps",
                },
                {
                    "q": "À quoi servent-ils ?",
                    "a": "Ils permettent de mieux utiliser le terrain lorsque les ressources sont limitées.",
                },
            ],
        },
        {
            "id": "conflictes",
            "title": "Conflits",
            "questions": [
                {
                    "q": "Qu'est-ce qu'un conflit dur ?",
                    "a": "C'est lorsque la même équipe ou personne doit être en deux endroits en même temps, ou que deux activités du club coïncident de manière incompatible.",
                    "link": "/season/{season_id}/conflicts",
                },
                {
                    "q": "Qu'est-ce qu'un conflit soft ?",
                    "a": "C'est un chevauchement ou une préférence qu'il convient de vérifier, mais qui n'empêche pas l'activité. AtempoSports le signale pour que vous le regardiez.",
                },
                {
                    "q": "Comment résoudre un conflit ?",
                    "a": "AtempoSports vous propose des alternatives. Vous pouvez les accepter, les modifier ou, si vous préférez, modifier manuellement l'activité depuis le calendrier.",
                },
            ],
        },
        {
            "id": "renovacio",
            "title": "Renouvellement de saison",
            "questions": [
                {
                    "q": "Comment commencer une nouvelle saison ?",
                    "a": "Allez dans Saisons et cliquez sur 'Renouveler'. AtempoSports copie la configuration actuelle (équipes, terrains et créneaux) et crée une nouvelle saison vide.",
                    "link": "/season/{season_id}/renew",
                },
                {
                    "q": "Qu'est-ce qui est copié ?",
                    "a": "La nouvelle saison réutilise le squelette de la précédente : équipes, terrains, créneaux et préférences. Cela permet au coordinateur d'ajuster les personnes, horaires et sessions à la nouvelle saison sans repartir de zéro. Les matchs et entraînements concrets, en revanche, ne sont pas copiés ; vous devez les créer ou les importer à nouveau pour la nouvelle saison.",
                },
                {
                    "q": "Puis-je avoir plus d'une saison ?",
                    "a": "Oui, mais une seule est active par club. Vous pouvez changer la saison active depuis le menu Saisons si vous êtes opérateur.",
                },
            ],
        },
        {
            "id": "ajustos",
            "title": "Paramètres du club",
            "questions": [
                {
                    "q": "Comment changer l'email du club ?",
                    "a": "Dans Paramètres du club (ou Club), vous pouvez enregistrer un nouvel email. C'est important pour pouvoir récupérer l'accès.",
                    "link": "/season/{season_id}/club",
                },
                {
                    "q": "Comment changer le mot de passe ?",
                    "a": "Sur la même page du club, indiquez le mot de passe actuel et le nouveau. Si vous ne vous souvenez plus de l'actuel, contactez la personne qui vous a donné accès.",
                },
            ],
        },
    ],
    "it": [
        {
            "id": "primeres-passos",
            "title": "Primi passi",
            "questions": [
                {
                    "q": "Come entro per la prima volta?",
                    "a": "Inserisci il codice del club e la password. Se l'hai dimenticata, clicca su 'Password dimenticata?'. Riceverai un link all'email del club se l'abbiamo configurata.",
                    "link": "/login",
                },
                {
                    "q": "Come cambio la password?",
                    "a": "Vai al menu del club ('Impostazioni') e inserisci una nuova password di almeno 8 caratteri. Assicurati di ricordarla o di avere un'email di recupero.",
                    "link": "/season/{season_id}/club",
                },
                {
                    "q": "Posso cambiare la lingua?",
                    "a": "Sì. In alto a destra troverai un selettore con tutte le lingue. La modifica interessa l'intera applicazione.",
                },
            ],
        },
        {
            "id": "federacio",
            "title": "Importa federazione",
            "questions": [
                {
                    "q": "Come cerco le partite federali?",
                    "a": "Vai a Importa, scrivi il nome del tuo club e scegli la federazione (RFEP o FECAPA) e la comunità autonoma. AtempoSports cercherà le convocazioni disponibili.",
                    "link": "/season/{season_id}/fed",
                },
                {
                    "q": "E se non trovo il mio club?",
                    "a": "Puoi aggiungere squadre e partite manualmente dalle sezioni Squadre e Partite. L'opzione di ricerca copre attualmente solo la Spagna e le sue comunità autonome.",
                },
                {
                    "q": "Si vedono le modifiche della federazione?",
                    "a": "Sì. Quando la federazione cambia gli orari, AtempoSports lo rileva e ti avvisa nella home page per farli rivedere prima di applicarli.",
                    "link": "/app",
                },
            ],
        },
        {
            "id": "pistes",
            "title": "Campi e fasce orarie",
            "questions": [
                {
                    "q": "Come aggiungo un campo?",
                    "a": "Vai a Campi e scrivi il nome. Poi definisci le fasce orarie disponibili (ad esempio, il lunedì dalle 18:00 alle 20:00).",
                    "link": "/season/{season_id}/venues",
                },
                {
                    "q": "Cos'è una fascia oraria?",
                    "a": "Una fascia è un orario in cui il campo è libero per allenarsi o giocare. Puoi avere diverse fasce al giorno e per campo.",
                },
                {
                    "q": "Posso bloccare una fascia?",
                    "a": "Se una fascia non è disponibile per gli allenamenti, puoi marcarla o eliminarla. Solo le fasce attive vengono usate per generare proposte.",
                },
            ],
        },
        {
            "id": "equips",
            "title": "Squadre e persone",
            "questions": [
                {
                    "q": "Come creo una squadra?",
                    "a": "Vai a Squadre e clicca su 'Crea squadra'. Puoi scrivere il nome manualmente o incollare un elenco di nomi se ne hai molti.",
                    "link": "/season/{season_id}/teams",
                },
                {
                    "q": "Cosa sono le persone?",
                    "a": "Giocatori, allenatori e altri membri che puoi collegare alle squadre. Questo consente ad AtempoSports di rilevare sovrapposizioni quando la stessa persona deve essere in due posti contemporaneamente.",
                    "link": "/season/{season_id}/people",
                },
                {
                    "q": "Come importo molti giocatori?",
                    "a": "In Persone puoi incollare nomi separati da righe o da virgole. È utile quando hai già un elenco del club.",
                },
            ],
        },
        {
            "id": "calendari",
            "title": "Calendario e partite",
            "questions": [
                {
                    "q": "Cosa vedo nel calendario?",
                    "a": "I prossimi 28 giorni con le partite federali, gli allenamenti già applicati e qualsiasi modifica in sospeso.",
                    "link": "/season/{season_id}/calendar",
                },
                {
                    "q": "Cosa significano i colori?",
                    "a": "Verde = tutto bene, giallo = possibile conflitto soft, rosso = conflitto duro da risolvere.",
                },
                {
                    "q": "Come sposto una partita?",
                    "a": "Da Partite o dal calendario puoi modificare l'ora. AtempoSports ti dirà se il nuovo orario crea conflitti con altre attività.",
                    "link": "/season/{season_id}/matches",
                },
            ],
        },
        {
            "id": "entrenaments",
            "title": "Allenamenti",
            "questions": [
                {
                    "q": "Come genero gli allenamenti?",
                    "a": "Vai ad Allenamenti, controlla le ore settimanali di ogni squadra e clicca su 'Proponi'. AtempoSports farà una bozza distribuendo le sessioni nelle fasce disponibili.",
                    "link": "/season/{season_id}/trainings",
                },
                {
                    "q": "Cos'è la bozza?",
                    "a": "È una proposta di allenamenti che non è ancora nel calendario ufficiale. Puoi modificarla, scartarla o applicarla.",
                },
                {
                    "q": "Come applico gli allenamenti?",
                    "a": "Se ti piace la bozza, clicca su 'Applica'. Questo sposta gli allenamenti nel calendario ufficiale e sostituisce quelli dell'ultimo lotto applicato.",
                },
                {
                    "q": "Posso annullare l'applicazione?",
                    "a": "Sì, a meno che tu non abbia generato una nuova bozza. C'è un'opzione 'Annulla applicazione' che riporta l'ultimo lotto in bozza.",
                },
            ],
        },
        {
            "id": "grups",
            "title": "Gruppi",
            "questions": [
                {
                    "q": "Cos'è un gruppo?",
                    "a": "Due o più unità che condividono la stessa fascia intera per tutta la stagione. Utile quando si allenano insieme.",
                    "link": "/season/{season_id}/trainings/groups",
                },
                {
                    "q": "Come creo un gruppo?",
                    "a": "Vai ad Allenamenti → Gruppi e seleziona le squadre o unità che si alleneranno insieme. AtempoSports assegnerà loro una fascia comune.",
                },
            ],
        },
        {
            "id": "solapaments",
            "title": "Sovrapposizioni",
            "questions": [
                {
                    "q": "Cos'è una sovrapposizione?",
                    "a": "È il modo in cui avviene il passaggio tra due squadre sullo stesso campo. Per esempio, la squadra A si allena fino alle 19:00 e la squadra B inizia alle 19:00. Si può far sovrapporre 15 o più minuti uno o più giorni o per tutta la stagione. Che la sovrapposizione implichi o meno la suddivisione del campo per ogni squadra è una questione da decidere tra allenatori e coordinatore.",
                    "link": "/season/{season_id}/trainings/overlaps",
                },
                {
                    "q": "A cosa servono?",
                    "a": "Permettono di sfruttare meglio il campo quando le risorse sono scarse.",
                },
            ],
        },
        {
            "id": "conflictes",
            "title": "Conflitti",
            "questions": [
                {
                    "q": "Cos'è un conflitto duro?",
                    "a": "È quando la stessa squadra o persona deve essere in due posti contemporaneamente, o due attività dello stesso club coincidono in modo incompatibile.",
                    "link": "/season/{season_id}/conflicts",
                },
                {
                    "q": "Cos'è un conflitto soft?",
                    "a": "È una sovrapposizione o preferenza che conviene rivedere, ma che non impedisce l'attività. AtempoSports te lo segnala per farlo controllare.",
                },
                {
                    "q": "Come risolvo un conflitto?",
                    "a": "AtempoSports ti propone alternative. Puoi accettarle, modificarle o, se preferisci, cambiare manualmente l'attività dal calendario.",
                },
            ],
        },
        {
            "id": "renovacio",
            "title": "Rinnovo stagione",
            "questions": [
                {
                    "q": "Come inizio una nuova stagione?",
                    "a": "Vai a Stagioni e clicca su 'Rinnova'. AtempoSports copia la configurazione attuale (squadre, campi e fasce) e crea una nuova stagione vuota.",
                    "link": "/season/{season_id}/renew",
                },
                {
                    "q": "Cosa viene copiato?",
                    "a": "La nuova stagione riutilizza lo scheletro della precedente: squadre, campi, fasce e preferenze. Questo permette al coordinatore di aggiustare persone, orari e sessioni alla nuova stagione senza ricominciare da zero. Le partite e gli allenamenti concreti, invece, non vengono copiati; devi crearli o importarli di nuovo per la nuova stagione.",
                },
                {
                    "q": "Posso avere più di una stagione?",
                    "a": "Sì, ma solo una è attiva per club. Puoi cambiare la stagione attiva dal menu Stagioni se sei operatore.",
                },
            ],
        },
        {
            "id": "ajustos",
            "title": "Impostazioni del club",
            "questions": [
                {
                    "q": "Come cambio l'email del club?",
                    "a": "In Impostazioni del club (o Club) puoi salvare una nuova email. È importante per poter recuperare l'accesso.",
                    "link": "/season/{season_id}/club",
                },
                {
                    "q": "Come cambio la password?",
                    "a": "Nella stessa pagina del club indica la password attuale e quella nuova. Se non ricordi quella attuale, contatta chi ti ha dato accesso.",
                },
            ],
        },
    ],
    "de": [
        {
            "id": "primeres-passos",
            "title": "Erste Schritte",
            "questions": [
                {
                    "q": "Wie melde ich mich zum ersten Mal an?",
                    "a": "Gib den Club-Code und das Passwort ein. Falls du es vergessen hast, klicke auf 'Passwort vergessen?'. Du erhältst einen Link an die Club-E-Mail, sofern wir diese konfiguriert haben.",
                    "link": "/login",
                },
                {
                    "q": "Wie ändere ich das Passwort?",
                    "a": "Gehe im Club-Menü zu 'Einstellungen' und gib ein neues Passwort mit mindestens 8 Zeichen ein. Merke es dir sicher oder hinterlege eine Wiederherstellungs-E-Mail.",
                    "link": "/season/{season_id}/club",
                },
                {
                    "q": "Kann ich die Sprache ändern?",
                    "a": "Ja. Oben rechts findest du eine Auswahl mit allen Sprachen. Die Änderung betrifft die gesamte Anwendung.",
                },
            ],
        },
        {
            "id": "federacio",
            "title": "Verband importieren",
            "questions": [
                {
                    "q": "Wie finde ich Verbandsspiele?",
                    "a": "Gehe zu Importieren, gib den Namen deines Clubs ein und wähle den Verband (RFEP oder FECAPA) sowie die autonome Gemeinschaft. AtempoSports sucht nach verfügbaren Ansetzungen.",
                    "link": "/season/{season_id}/fed",
                },
                {
                    "q": "Was, wenn ich meinen Club nicht finde?",
                    "a": "Du kannst Mannschaften und Spiele manuell über die Bereiche Mannschaften und Spiele hinzufügen. Die Suchoption deckt derzeit nur Spanien und seine autonomen Gemeinschaften ab.",
                },
                {
                    "q": "Werden Verbandsänderungen übernommen?",
                    "a": "Ja. Wenn der Verband Zeiten ändert, erkennt AtempoSports dies und benachrichtigt dich auf der Startseite, damit du sie vor dem Anwenden prüfst.",
                    "link": "/app",
                },
            ],
        },
        {
            "id": "pistes",
            "title": "Plätze und Zeitfenster",
            "questions": [
                {
                    "q": "Wie füge ich einen Platz hinzu?",
                    "a": "Gehe zu Plätze und gib den Namen ein. Definiere dann die verfügbaren Zeitfenster (z. B. montags von 18:00 bis 20:00 Uhr).",
                    "link": "/season/{season_id}/venues",
                },
                {
                    "q": "Was ist ein Zeitfenster?",
                    "a": "Ein Zeitfenster ist eine Zeit, in der der Platz frei zum Trainieren oder Spielen ist. Du kannst mehrere Fenster pro Tag und pro Platz haben.",
                },
                {
                    "q": "Kann ich ein Zeitfenster blockieren?",
                    "a": "Wenn ein Zeitfenster nicht für Training verfügbar ist, kannst du es markieren oder entfernen. Nur aktive Fenster werden zur Generierung von Vorschlägen verwendet.",
                },
            ],
        },
        {
            "id": "equips",
            "title": "Mannschaften und Personen",
            "questions": [
                {
                    "q": "Wie erstelle ich eine Mannschaft?",
                    "a": "Gehe zu Mannschaften und klicke auf 'Mannschaft erstellen'. Du kannst den Namen manuell eingeben oder eine Liste von Namen einfügen, wenn es viele sind.",
                    "link": "/season/{season_id}/teams",
                },
                {
                    "q": "Was sind Personen?",
                    "a": "Spieler, Trainer und andere Mitglieder, die du Mannschaften zuordnen kannst. So kann AtempoSports Überschneidungen erkennen, wenn dieselbe Person gleichzeitig an zwei Orten sein muss.",
                    "link": "/season/{season_id}/people",
                },
                {
                    "q": "Wie importiere ich viele Spieler?",
                    "a": "Unter Personen kannst du Namen zeilen- oder kommagetrennt einfügen. Das ist nützlich, wenn du bereits eine Club-Liste hast.",
                },
            ],
        },
        {
            "id": "calendari",
            "title": "Kalender und Spiele",
            "questions": [
                {
                    "q": "Was sehe ich im Kalender?",
                    "a": "Die nächsten 28 Tage mit Verbandsspielen, bereits angewendeten Trainingseinheiten und ausstehenden Änderungen.",
                    "link": "/season/{season_id}/calendar",
                },
                {
                    "q": "Was bedeuten die Farben?",
                    "a": "Grün = alles in Ordnung, Gelb = möglicher weicher Konflikt, Rot = harter Konflikt, der gelöst werden muss.",
                },
                {
                    "q": "Wie verschiebe ich ein Spiel?",
                    "a": "Über Spiele oder den Kalender kannst du die Uhrzeit bearbeiten. AtempoSports zeigt dir an, ob der neue Termin Konflikte mit anderen Aktivitäten erzeugt.",
                    "link": "/season/{season_id}/matches",
                },
            ],
        },
        {
            "id": "entrenaments",
            "title": "Trainingseinheiten",
            "questions": [
                {
                    "q": "Wie generiere ich Trainingseinheiten?",
                    "a": "Gehe zu Trainingseinheiten, prüfe die Wochenstunden jeder Mannschaft und klicke auf 'Vorschlagen'. AtempoSports erstellt einen Entwurf, der die Einheiten auf die verfügbaren Zeitfenster verteilt.",
                    "link": "/season/{season_id}/trainings",
                },
                {
                    "q": "Was ist der Entwurf?",
                    "a": "Es ist ein Vorschlag für Trainingseinheiten, der noch nicht im offiziellen Kalender steht. Du kannst ihn ändern, verwerfen oder anwenden.",
                },
                {
                    "q": "Wie wende ich Trainingseinheiten an?",
                    "a": "Wenn dir der Entwurf gefällt, klicke auf 'Anwenden'. Dadurch werden die Trainingseinheiten in den offiziellen Kalender übernommen und die zuletzt angewendeten Einheiten ersetzt.",
                },
                {
                    "q": "Kann ich die Anwendung rückgängig machen?",
                    "a": "Ja, solange du keinen neuen Entwurf erstellt hast. Es gibt eine Option 'Anwendung rückgängig machen', die den letzten Vorschlag wieder in den Entwurf zurückversetzt.",
                },
            ],
        },
        {
            "id": "grups",
            "title": "Gruppen",
            "questions": [
                {
                    "q": "Was ist eine Gruppe?",
                    "a": "Zwei oder mehr Einheiten, die während der ganzen Saison denselben vollen Zeitfenster teilen. Nützlich, wenn sie gemeinsam trainieren.",
                    "link": "/season/{season_id}/trainings/groups",
                },
                {
                    "q": "Wie erstelle ich eine Gruppe?",
                    "a": "Gehe zu Trainingseinheiten → Gruppen und wähle die Mannschaften oder Einheiten aus, die zusammen trainieren. AtempoSports weist ihnen ein gemeinsames Zeitfenster zu.",
                },
            ],
        },
        {
            "id": "solapaments",
            "title": "Überschneidungen",
            "questions": [
                {
                    "q": "Was ist eine Überschneidung?",
                    "a": "Es ist die Art und Weise, wie der Übergang zwischen zwei Mannschaften auf demselben Platz erfolgt. Zum Beispiel trainiert Mannschaft A bis 19:00 Uhr und Mannschaft B beginnt um 19:00 Uhr. Man kann eine Überschneidung von 15 oder mehr Minuten an einem oder mehreren Tagen oder die ganze Saison über einrichten. Ob die Überschneidung eine Aufteilung des Platzes für jede Mannschaft bedeutet oder nicht, ist eine Entscheidung, die Trainer und Koordinator treffen.",
                    "link": "/season/{season_id}/trainings/overlaps",
                },
                {
                    "q": "Wozu dienen sie?",
                    "a": "Sie ermöglichen eine bessere Nutzung des Platzes, wenn die Ressourcen knapp sind.",
                },
            ],
        },
        {
            "id": "conflictes",
            "title": "Konflikte",
            "questions": [
                {
                    "q": "Was ist ein harter Konflikt?",
                    "a": "Wenn dieselbe Mannschaft oder Person gleichzeitig an zwei Orten sein muss oder wenn zwei Club-Aktivitäten unvereinbar übereinanderfallen.",
                    "link": "/season/{season_id}/conflicts",
                },
                {
                    "q": "Was ist ein weicher Konflikt?",
                    "a": "Es ist eine Überschneidung oder Präferenz, die es lohnt zu prüfen, aber die Aktivität nicht verhindert. AtempoSports markiert sie, damit du sie dir ansiehst.",
                },
                {
                    "q": "Wie löse ich einen Konflikt?",
                    "a": "AtempoSports schlägt Alternativen vor. Du kannst sie annehmen, ändern oder die Aktivität bei Bedarf manuell im Kalender anpassen.",
                },
            ],
        },
        {
            "id": "renovacio",
            "title": "Saisonverlängerung",
            "questions": [
                {
                    "q": "Wie beginne ich eine neue Saison?",
                    "a": "Gehe zu Saisons und klicke auf 'Verlängern'. AtempoSports kopiert die aktuelle Konfiguration (Mannschaften, Plätze und Zeitfenster) und erstellt eine leere neue Saison.",
                    "link": "/season/{season_id}/renew",
                },
                {
                    "q": "Was wird kopiert?",
                    "a": "Die neue Saison nutzt das Gerüst der vorherigen: Mannschaften, Plätze, Zeitfenster und Präferenzen. So kann der Koordinator Personen, Zeiten und Sitzungen für die neue Saison anpassen, ohne bei Null anzufangen. Konkrete Spiele und Trainingseinheiten werden jedoch nicht kopiert; du musst sie für die neue Saison neu erstellen oder importieren.",
                },
                {
                    "q": "Kann ich mehr als eine Saison haben?",
                    "a": "Ja, aber nur eine ist pro Club aktiv. Wenn du Betreiber bist, kannst du die aktive Saison im Saison-Menü wechseln.",
                },
            ],
        },
        {
            "id": "ajustos",
            "title": "Club-Einstellungen",
            "questions": [
                {
                    "q": "Wie ändere ich die Club-E-Mail?",
                    "a": "In Club-Einstellungen (oder Club) kannst du eine neue E-Mail speichern. Das ist wichtig, um den Zugriff wiederherstellen zu können.",
                    "link": "/season/{season_id}/club",
                },
                {
                    "q": "Wie ändere ich das Passwort?",
                    "a": "Auf derselben Club-Seite gibst du das aktuelle und das neue Passwort ein. Falls du das aktuelle nicht mehr kennst, wende dich an die Person, die dir den Zugang gegeben hat.",
                },
            ],
        },
    ],
}

HELP.update(EXTRA_HELP)


def get_help(lang: str) -> list[dict]:
    """Retorna l'ajuda en l'idioma demanat, o en català si encara no existeix."""
    return HELP.get(lang, HELP["ca"])
