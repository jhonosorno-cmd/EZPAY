> **PRELIMINAR — en construcción.** Casos de uso que ML 2 usará como base del catálogo de pruebas de aceptación. Aún no es spec ni está ratificado por el equipo.

Autenticación:
1. Un usuario puede autenticarse con credenciales (correo/usuario - contraseña (definir como es))
2. Autenticación fallida para correos o usuarios incompletos o con caracteres no permitidos
3. Autenticación fallida para contraseñas que no cumplan con requisitos mínimos --- Definir
4. Después de la autenticación con user & password, si el usuario es nuevo el sistema debe solicitar grabar 3 audios para reconocimiento de voz. Se debe mostrar el texto que el usuario
	debe de leer en voz alta para completar la autenticación.
5. Si el usuario ya se encontraba registrado, el sistema debe comprobar que los audios ya fueron grabados y NO SOLICITAR LA GRABACIÓN
6. Al solicitar los 3 audios, debe permitir un botón de "Iniciar grabación" - Debe mostrar el texto a leer del primer audio.
7. Al hacer click en el botón de "Iniciar Grabación", debe habilitarse el micrófono y comenzar a grabar audio. - Debe mostrar el texto a leer del primer audio.
8. Durante la grabación, debe aparecer un botón de "Detener Grabación" - Debe mostrar el texto a leer del primer audio.
9. Al dar click en el botón de "Detener Grabación", debe detenerse la grabación y desactivar el micrófono del equipo.
10. Si el audio dura menos de 3 segundos, debe rechazarlo y volver al paso 6.
11. Al detener la grabación, el sistema debe mostrar un botón de "reproducir grabación", uno de "repetir grabación y uno de "utilizar grabación"
12. Si se da click en "Reproducir Grabación", el audio debe reproducirse.
13. Si se da click en "Repetir Grabación", debe aparecer un aviso para confirmar la acción y volver al caso 7. - Mostrando el texto del primer audio.
14. Si se da click en "Utilizar Grabación", se pasa al siguiente audio y se repite del caso 7 al 13 hasta completar 3 audios. - Se cambia el texto para el segundo audio y luego para el tercero.
15. Al completar la grabación de los 3 audios, muestra un aviso de completado y posteriormente un menú.
	Menú:
		Información Personal
		Contactos + Opción de Registro
		Balance -- Expansión: Billeteras en diferentes Divisas
		Wallet Address
		Presupuesto semanal restante.
		Funciones:
			Definir presupuesto semanal
			Enviar
		Historial
		Configuración

Funcionalidades
Definir Presupuesto
1. Al hacer click en "Definir presupuesto semanal", debe salir una pantalla con "Dime tu presupuesto semanal para transferencias" - La pantalla debe mostrar un teclado numérico y mostrar la divisa de la wallet (puede permitir seleccionar divisas) - Debe haber un botón de aceptar.
2. Al hacer click en "Aceptar", se comienza a aprobar el presupuesto -- Se realiza el protocolo de OP para el grant de un presupuesto.
	2.1. El monto ingresado debe ser el liimt que utilice el grant.
3. Para aprobar el presupuesto, debe hacerse de manera interactiva, según la documentación.
4. Al aprobarse, debe aparecer una pantalla de confirmación que muestre el presupuesto definido con un botón de aceptar.
5. Al darle "Aceptar" se debe cerrar la pantalla

Enviar
1. Al hacer click en "Enviar Dinero", debe salir una pantalla con: "Di el monto y el destinatario" además de un botón para comenzar a grabar.
2. Al hacer click en "Grabar", se activa el micrófono y comienza a grabar audio.
3. Durante la grabación, debe aparecer un botón de detener grabación.
4. Al hacer click en "Detener Grabación" debe detenerse la grabación y desactivar el micrófono del equipo.
5. Si el audio dura menos de 3 segundos, debe rechazarlo y volver al paso 2.
6. Al detener la grabación, el sistema debe mostrar un botón de "reproducir grabación", uno de "repetir grabación y uno de "utilizar grabación"
7. Si se da click en "Reproducir Grabación", el audio debe reproducirse.
8. Si se da click en "Repetir Grabación", debe aparecer un aviso para confirmar la acción.
9. Si se da click en "Utilizar Grabación", se comienza a hacer la transacción.
	9.1. Cuando se da a utilizar grabación, se hace el proceso de speech-to-text: se guarda en un JSON file con los datos de: intención, destinatario, monto, divisa.
	9.2. El monto del JSON debe ser el amount del outgoing payment.
10. Para aprobar el grant del outgoing payment, debe hacerse de manera interactiva según la documentación.
11. Al aprobarse la transacción, debe aparecer una pantalla de confirmación con: "Se envió [amount] [divisa] a [destinatario]" y "Presupuesto semanal restante: [remaining] [divisa]". Debe tener un botón de "Aceptar"
12 Al darle "Aceptar" se debe cerrar la pantalla.

