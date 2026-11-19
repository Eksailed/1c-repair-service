import argparse
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXE = Path(r"C:\Program Files (x86)\1cv8t\8.3.27.1508\bin\1cv8t.exe")


def check(exe, dump, work, benchmark=False):
    base = work / "База"
    source = work / "Исходники"
    source.mkdir()
    log = work / "1c.log"
    result = work / "result.txt"

    def run(mode, *args):
        log.unlink(missing_ok=True)
        process = subprocess.run(
            [exe, mode, *args, "/Out", log, "/DisableStartupDialogs", "/DisableStartupMessages"],
            timeout=45,
        )
        if log.exists():
            print(log.read_text(encoding="utf-8-sig"), end="", flush=True)
        process.check_returncode()

    def designer(*args):
        run("DESIGNER", "/F", base, *args)

    run("CREATEINFOBASE", f"File={base};")
    designer("/RestoreIB", dump)
    designer("/CheckConfig", "-ConfigLogIntegrity", "-ThinClient", "-Server", "-ExtendedModulesCheck")
    designer("/DumpConfigToFiles", source)

    config = source / "Configuration.xml"
    xml = config.read_text(encoding="utf-8-sig")
    header = xml.splitlines()[1]
    config.write_text(
        xml.replace("</ChildObjects>", "<CommonModule>ПроверкаПортфолио</CommonModule></ChildObjects>", 1),
        encoding="utf-8-sig",
    )
    common = source / "CommonModules"
    (common / "ПроверкаПортфолио.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n' + header
        + f'<CommonModule uuid="{uuid4()}"><Properties><Name>ПроверкаПортфолио</Name>'
        + "<Server>true</Server><ServerCall>true</ServerCall></Properties></CommonModule></MetaDataObject>",
        encoding="utf-8-sig",
    )
    module = common / "ПроверкаПортфолио" / "Ext" / "Module.bsl"
    module.parent.mkdir(parents=True)
    scenario = Path(__file__).with_suffix(".bsl")
    if benchmark:
        scenario = scenario.with_name("замер-складского-отчёта.bsl")
    module.write_text(scenario.read_text(encoding="utf-8-sig"), encoding="utf-8-sig")
    startup = source / "Ext" / "ManagedApplicationModule.bsl"
    startup.parent.mkdir(exist_ok=True)
    startup.write_text(f"""
Процедура ПриНачалеРаботыСистемы()
    Итог = "OK";
    Попытка
        {"Итог = ПроверкаПортфолио.ИзмеритьОтчет();" if benchmark else "ПроверкаПортфолио.ПроверитьСценарий();"}
    Исключение
        Итог = ПодробноеПредставлениеОшибки(ИнформацияОбОшибке());
    КонецПопытки;
    ФайлРезультата = Новый ЗаписьТекста("{result}", КодировкаТекста.UTF8);
    ФайлРезультата.ЗаписатьСтроку(Итог);
    ФайлРезультата.Закрыть();
    ЗавершитьРаботуСистемы(Ложь);
КонецПроцедуры
""", encoding="utf-8-sig")
    designer("/LoadConfigFromFiles", source)
    designer("/UpdateDBCfg")
    designer("/CheckConfig", "-ThinClient", "-Server", "-ExtendedModulesCheck")
    run("ENTERPRISE", "/F", base)
    outcome = result.read_text(encoding="utf-8-sig").strip()
    if benchmark and outcome.startswith("OK\n"):
        print(outcome.removeprefix("OK\n"))
    elif outcome != "OK":
        raise RuntimeError(outcome)
    else:
        print("Функциональные проверки портфолио прошли, включая закупки и резервирование.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Проверка демонстрационной базы 1С")
    parser.add_argument("--exe", type=Path, default=DEFAULT_EXE, help="Путь к 1cv8t.exe")
    parser.add_argument("--dump", type=Path, default=ROOT / "ЗаявкиНаРемонт-Резервы-Демо.dt", help="Путь к выгрузке .dt")
    parser.add_argument("--benchmark", action="store_true", help="Замер времени складского отчёта")
    options = parser.parse_args()
    with TemporaryDirectory(prefix="repair-check-") as folder:
        check(options.exe.resolve(strict=True), options.dump.resolve(strict=True), Path(folder), options.benchmark)
