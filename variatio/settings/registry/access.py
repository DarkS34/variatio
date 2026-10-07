"""Who may try more often: the networks a whole class reaches the installation from."""

import ipaddress

from ..types import Impact, Setting, SettingError

# A network wider than this cannot be one school's: refusing it keeps the list from turning
# the per-address limit off for half the Internet.
MIN_PREFIX = {4: 8, 6: 32}


def networks(value: object) -> list[str]:
    """Return each network in its canonical form, refusing what is not one or is too wide.

    A single address is its own network (`/32`, `/128`); host bits are dropped, so
    `10.1.2.3/16` is stored as `10.1.0.0/16`. A network written twice is kept once.
    """
    out: list[str] = []
    for item in value if isinstance(value, list) else []:
        try:
            network = ipaddress.ip_network(str(item).strip(), strict=False)
        except ValueError:
            raise SettingError(
                f"«{item}» no es una red: escríbela como 192.168.1.0/24 o como una sola dirección"
            ) from None
        floor = MIN_PREFIX[network.version]
        if network.prefixlen < floor:
            raise SettingError(
                f"«{item}» es demasiado amplia para ser la red de un centro: "
                f"la máscara tiene que ser /{floor} o más"
            )
        if str(network) not in out:
            out.append(str(network))
    return out


SETTINGS = [
    Setting(
        key="access.trusted_networks",
        name="TRUSTED_NETWORKS",
        kind="list[str]",
        default=[],
        group="Acceso",
        impact=Impact.NONE,
        env="VARIATIO_TRUSTED_NETWORKS",
        clean=networks,
        doc="""Las redes desde las que muchas personas entran con una sola dirección: la de un centro,
detrás de su NAT. Un intento desde una de estas redes no cuenta en el límite por dirección
(entrar admite 8 intentos en 5 minutos por dirección, los correctos incluidos), que en un aula
dejaba fuera al noveno alumno. El límite por cuenta, o por enlace, cuenta siempre, también
desde aquí: probar contraseñas contra una cuenta sigue cerrado. Lo que no tiene cuenta que
contar (restablecer una contraseña) sigue contando la dirección.

Solo redes propias del centro, nunca 0.0.0.0/0: se rechaza una red de máscara menor que /8 en
IPv4 o que /32 en IPv6. Una dirección sola vale como su propia red. Detrás de un proxy, la
dirección es la que escribe el proxy (VARIATIO_TRUST_PROXY=1).

Se lee en cada intento: un cambio vale en la petición siguiente, sin reiniciar.""",
    ),
]
