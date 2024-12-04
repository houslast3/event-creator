import subprocess
import sys
import pkg_resources
from pkg_resources import DistributionNotFound, VersionConflict

def get_installed_version(package_name):
    try:
        return pkg_resources.get_distribution(package_name).version
    except (DistributionNotFound, VersionConflict):
        return None

def install_package(package_name, version=None):
    package_spec = f"{package_name}=={version}" if version else package_name
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_spec])
        print(f"✓ Instalado {package_name}" + (f" versão {version}" if version else ""))
        return True
    except subprocess.CalledProcessError:
        print(f"✗ Erro ao instalar {package_name}")
        return False

def main():
    # Lista de dependências com versões compatíveis
    dependencies = {
        'flask': '2.3.3',
        'flask-sqlalchemy': '3.1.1',
        'flask-login': '0.6.2',
        'flask-socketio': '5.3.6',
        'werkzeug': '2.3.7',
        'python-socketio': '5.9.0',
        'eventlet': '0.33.3'
    }
    
    print("\n🔍 Verificando dependências instaladas...\n")
    
    for package, version in dependencies.items():
        installed_version = get_installed_version(package)
        
        if installed_version:
            if installed_version == version:
                print(f"✓ {package} já está instalado na versão correta ({version})")
            else:
                print(f"⚠ {package} está instalado na versão {installed_version}, atualizando para {version}...")
                install_package(package, version)
        else:
            print(f"➤ Instalando {package} versão {version}...")
            install_package(package, version)
    
    print("\n✨ Instalação de dependências concluída!")

if __name__ == "__main__":
    main()
