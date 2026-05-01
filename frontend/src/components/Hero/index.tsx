import Link from "next/link";

const Hero = () => {
  return (
    <>
      <section
        id="home"
        className="relative z-10 overflow-hidden pb-16 pt-[120px] md:pb-[120px] md:pt-[150px] xl:pb-[160px] xl:pt-[180px] 2xl:pb-[200px] 2xl:pt-[210px]"
        style={{
          backgroundImage: "url('https://media.istockphoto.com/id/1216891632/photo/young-scientists-biologists-or-researchers-putting-personal-protective-equipments-to-prevent.jpg?s=170667a&w=0&k=20&c=KJRZgAA7-rh-Xe2d70MKwVx7kO7TeDa7KTFifcX0tp8=')",
          backgroundSize: "cover",
          backgroundPosition: "center",
        }}
      >
        <div className="absolute inset-0 z-[-1] bg-black/40"></div>
        <div className="container">
          <div className="-mx-4 flex flex-wrap">
            <div className="w-full px-4">
              <div className="ml-auto mr-0 max-w-[800px] text-right">
                <h1 className="mb-5 text-4xl font-extrabold leading-tight text-white sm:text-5xl sm:leading-tight md:text-6xl md:leading-tight drop-shadow-md">
                  DEX-LAB: The Virtual<br />Laboratory for AI<br />Drug Discovery
                </h1>
                <p className="mb-12 text-base font-medium leading-relaxed! text-white sm:text-lg md:text-xl drop-shadow-md">
                  DEX-LAB is a next-generation platform that orchestrates specialized AI agents to screen 100+ million compounds in real-time. We reduce development time from 15 years to 24 hours, making life-saving breakthroughs accessible and affordable.
                </p>
                <div className="flex flex-col items-end justify-end space-y-4 sm:flex-row sm:space-x-4 sm:space-y-0">
                  <Link
                    href="#features"
                    className="rounded-xs bg-primary px-8 py-4 text-base font-semibold text-white duration-300 ease-in-out hover:bg-primary/80 shadow-btn"
                  >
                    Explore More
                  </Link>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>
    </>
  );
};

export default Hero;
